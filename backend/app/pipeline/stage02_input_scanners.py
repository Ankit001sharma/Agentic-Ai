"""Stage 2 — Input Scanners.

Runs ALL registered scanners in parallel (asyncio.gather).
No LLM calls at this stage — pure deterministic + ML-model scanning only.
"""

from __future__ import annotations

import asyncio
from typing import Any

import redis.asyncio as aioredis

from app.core.logging import get_logger
from app.pipeline.base import Stage
from app.scanners.base import Scanner, ScannerResult
from app.schemas.sentinel import Finding, ScanState

log = get_logger("pipeline.stage02")


def _build_default_scanners() -> list[Scanner]:
    """Instantiate all available scanners; skip any with missing deps."""
    scanners: list[Scanner] = []  # type: ignore[type-arg]

    def _try(module: str, cls: str) -> None:
        try:
            import importlib
            mod = importlib.import_module(module)
            scanners.append(getattr(mod, cls)())
        except Exception as exc:  # noqa: BLE001
            log.warning("scanner_unavailable", scanner=cls, error=str(exc))

    # All 12 Stage-2 scanners from the architecture diagram
    _try("app.scanners.regex_rules",         "RegexRulesScanner")
    _try("app.scanners.presidio_pii",        "PresidioPIIScanner")
    _try("app.scanners.secrets_scan",        "SecretsScanScanner")
    _try("app.scanners.toxicity",            "ToxicityScanner")
    _try("app.scanners.code_ip",             "CodeIPScanner")
    _try("app.scanners.embedding_jailbreak", "EmbeddingJailbreakScanner")
    _try("app.scanners.vector_recall",       "VectorRecallScanner")
    _try("app.scanners.malware_request",     "MalwareRequestScanner")
    _try("app.scanners.rbac",                "RBACScanner")
    _try("app.scanners.internal_info",       "InternalInfoScanner")
    _try("app.scanners.nhi_check",           "NHIScanner")
    _try("app.scanners.rate_limit",          "RateLimitAbuseScanner")

    return scanners


class InputScannersStage(Stage):
    def __init__(
        self,
        scanners: list[Scanner] | None = None,
        redis_client: aioredis.Redis | None = None,
    ) -> None:
        self._scanners = scanners if scanners is not None else _build_default_scanners()
        self._redis = redis_client

    async def run(self, state: ScanState) -> ScanState:
        state.pipeline_stage = 2

        if not self._scanners:
            log.warning("no_scanners_configured")
            return state

        # Flatten user context so scanners key on individual fields directly
        # rather than drilling into the nested user dict.
        user_dict = state.user.model_dump()
        scan_ctx: dict[str, Any] = {
            "user": user_dict,
            "user_id": state.user.user_id,
            "role": state.user.role,
            "auth_type": state.user.auth_type,
            "resource": state.user.resource,
            "redis_client": self._redis,
        }

        # VectorRecallScanner needs a live DB session; open one for the whole
        # Stage 2 batch to share across all scanners and avoid N connections.
        from app.db.session import SessionLocal

        async with SessionLocal() as db_session:
            scan_ctx["db_session"] = db_session

            results: list[ScannerResult | BaseException] = await asyncio.gather(
                *[s.scan(state.prompt, **scan_ctx) for s in self._scanners],
                return_exceptions=True,
            )

        new_findings: list[Finding] = []
        for scanner, result in zip(self._scanners, results):
            if isinstance(result, BaseException):
                log.warning(
                    "scanner_error",
                    scanner=type(scanner).__name__,
                    error=str(result),
                )
                continue
            for f in result.findings:
                new_findings.append(
                    Finding(
                        category=f.category,
                        severity=f.severity,
                        scanner=f.scanner,
                        evidence=f.evidence,
                        metadata=f.metadata,
                    )
                )

        state.findings = list(state.findings) + new_findings
        log.info(
            "stage02_done",
            request_id=state.request_id,
            num_scanners=len(self._scanners),
            num_findings=len(new_findings),
        )
        return state

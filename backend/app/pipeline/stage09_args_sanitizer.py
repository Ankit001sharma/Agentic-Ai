"""Stage 9 — Tool-Args Sanitizer.

Re-runs the fast scanners (Presidio PII + Regex) over every generated tool
argument value before execution.  Any finding that crosses the BLOCK threshold
short-circuits the pipeline.
"""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.risk import aggregate
from app.pipeline.base import Stage
from app.schemas.sentinel import Finding, ScanState, Verdict

log = get_logger("pipeline.stage09")


def _args_to_text(args: dict) -> str:
    """Flatten tool args dict to a single string for scanning."""
    parts: list[str] = []
    for k, v in args.items():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            parts.extend(str(i) for i in v)
        else:
            parts.append(str(v))
    return " ".join(parts)


class ArgsanitizerStage(Stage):
    async def run(self, state: ScanState) -> ScanState:
        state.pipeline_stage = 9
        s = get_settings()

        if not state.tool_args or state.verdict == Verdict.BLOCK:
            return state

        text_to_scan = _args_to_text(state.tool_args)
        if not text_to_scan.strip():
            return state

        user_dict = state.user.model_dump()
        new_findings: list[Finding] = []

        # Only run fast, non-LLM scanners for args
        scanners_to_run = []
        for mod_cls in [
            ("app.scanners.presidio_pii", "PresidioPIIScanner"),
            ("app.scanners.regex_rules", "RegexRulesScanner"),
            ("app.scanners.secrets_scan", "SecretsScanScanner"),
        ]:
            try:
                import importlib
                mod = importlib.import_module(mod_cls[0])
                scanners_to_run.append(getattr(mod, mod_cls[1])())
            except Exception as exc:  # noqa: BLE001
                log.warning("stage09_scanner_load_fail", scanner=mod_cls[1], error=str(exc))

        if scanners_to_run:
            results = await asyncio.gather(
                *[sc.scan(text_to_scan, user=user_dict) for sc in scanners_to_run],
                return_exceptions=True,
            )
            for result in results:
                if isinstance(result, BaseException):
                    continue
                for f in result.findings:
                    new_findings.append(
                        Finding(
                            category=f.category,
                            severity=f.severity,
                            scanner=f"args_{f.scanner}",
                            evidence=f.evidence,
                            metadata={**f.metadata, "source": "tool_args"},
                        )
                    )

        if new_findings:
            # Always merge findings so the audit trail is complete regardless of verdict
            state.findings = list(state.findings) + new_findings

            # Recompute the global risk score across ALL findings (input + args)
            # so downstream stages (12 reporting, 13 adaptive risk) see a score
            # that reflects everything we know — not just Stage 3's snapshot.
            total_score, total_breakdown = aggregate(
                state.findings, state.user.historical_risk
            )
            state.risk = total_score
            state.risk_breakdown = total_breakdown

            # Independent BLOCK gate based on args-only score (so a previously
            # benign input + risky args still trips the gate).
            arg_score, _ = aggregate(new_findings)
            if arg_score >= s.risk_escalate_max:
                state.verdict = Verdict.BLOCK
                state.block_reason = (
                    f"Tool args failed sanitizer (score={arg_score}): "
                    f"{[f.category for f in new_findings[:3]]}"
                )
                log.warning(
                    "stage09_block",
                    request_id=state.request_id,
                    arg_score=arg_score,
                    total_risk=total_score,
                    tool_id=state.tool_id,
                )
            else:
                log.info(
                    "stage09_findings",
                    request_id=state.request_id,
                    num=len(new_findings),
                    arg_score=arg_score,
                    total_risk=total_score,
                )
        else:
            log.info("stage09_clean", request_id=state.request_id)

        return state

"""Security scanner tools (wrap existing scanners)."""

from __future__ import annotations

import time
from typing import Any

from app.core.policies import OPAClient
from app.db.session import SessionLocal
from app.scanners.code_ip import CodeIPScanner
from app.scanners.embedding_jailbreak import EmbeddingJailbreakScanner
from app.scanners.internal_info import InternalInfoScanner
from app.scanners.malware_request import MalwareRequestScanner
from app.scanners.nhi_check import NHIScanner
from app.scanners.presidio_pii import PIIPresidioScanner
from app.scanners.rbac import RBACScanner
from app.scanners.regex_rules import RegexScanner
from app.scanners.secrets_scan import SecretsScanner
from app.scanners.toxicity import ToxicityScanner
from app.scanners.vector_recall import VectorRecallScanner
from app.schemas.sentinel import ScanState, Verdict
from app.agents.tools.base import ToolResult

_REGEX = RegexScanner()
_PII = PIIPresidioScanner()
_SECRETS = SecretsScanner()
_TOX = ToxicityScanner()
_CODE = CodeIPScanner()
_EMBED = EmbeddingJailbreakScanner()
_RECALL = VectorRecallScanner()
_MALWARE = MalwareRequestScanner()
_RBAC = RBACScanner()
_INTERNAL = InternalInfoScanner()
_NHI = NHIScanner()
_OPA = OPAClient()

_llm_judge: Any = None


def _judge() -> Any:
    global _llm_judge
    if _llm_judge is None:
        from app.scanners.llm_judge import LLMJudgeScanner

        _llm_judge = LLMJudgeScanner()
    return _llm_judge


async def tool_scan_pii(text: str, state: ScanState) -> ToolResult:
    t0 = time.perf_counter()
    r = await _PII.scan(text)
    return ToolResult(
        ok=True,
        name="scan_pii",
        summary=f"findings={len(r.findings)} max_score={r.score:.2f}",
        data={"findings": [f.model_dump() for f in r.findings], "score": r.score},
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )


async def tool_scan_secrets(text: str, state: ScanState) -> ToolResult:
    t0 = time.perf_counter()
    r = await _SECRETS.scan(text)
    return ToolResult(
        ok=True,
        name="scan_secrets",
        summary=f"findings={len(r.findings)}",
        data={"findings": [f.model_dump() for f in r.findings], "score": r.score},
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )


async def tool_scan_injection(text: str, state: ScanState) -> ToolResult:
    t0 = time.perf_counter()
    a, b = await _REGEX.scan(text), await _EMBED.scan(text)
    return ToolResult(
        ok=True,
        name="scan_injection",
        summary="regex+embed",
        data={
            "findings": [f.model_dump() for f in a.findings + b.findings],
            "score": max(a.score, b.score),
        },
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )


async def tool_scan_toxicity(text: str, state: ScanState) -> ToolResult:
    t0 = time.perf_counter()
    r = await _TOX.scan(text)
    return ToolResult(
        ok=True,
        name="scan_toxicity",
        summary=f"score={r.score:.2f}",
        data={"findings": [f.model_dump() for f in r.findings], "score": r.score},
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )


async def tool_scan_malware(text: str, state: ScanState) -> ToolResult:
    t0 = time.perf_counter()
    r = await _MALWARE.scan(text)
    return ToolResult(
        ok=True,
        name="scan_malware",
        summary=f"findings={len(r.findings)}",
        data={"findings": [f.model_dump() for f in r.findings], "score": r.score},
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )


async def tool_check_rbac(text: str, state: ScanState) -> ToolResult:
    t0 = time.perf_counter()
    ctx = {
        "user_id": state.user.user_id,
        "role": state.user.role,
        "resource": state.user.resource,
        "auth_type": state.user.auth_type,
    }
    r = await _RBAC.scan(text, **ctx)
    return ToolResult(
        ok=True,
        name="check_rbac",
        summary=f"findings={len(r.findings)}",
        data={"findings": [f.model_dump() for f in r.findings], "score": r.score},
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )


async def tool_recall_vector(text: str, state: ScanState) -> ToolResult:
    t0 = time.perf_counter()
    async with SessionLocal() as db:
        ctx = {"user_id": state.user.user_id, "db_session": db}
        r = await _RECALL.scan(text, **ctx)
    return ToolResult(
        ok=True,
        name="recall_similar",
        summary=f"findings={len(r.findings)}",
        data={"findings": [f.model_dump() for f in r.findings], "score": r.score},
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )


async def tool_scan_code_ip(text: str, state: ScanState) -> ToolResult:
    t0 = time.perf_counter()
    r = await _CODE.scan(text)
    return ToolResult(
        ok=True,
        name="scan_code_ip",
        summary=f"findings={len(r.findings)} score={r.score:.2f}",
        data={"findings": [f.model_dump() for f in r.findings], "score": r.score},
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )


async def tool_scan_internal(text: str, state: ScanState) -> ToolResult:
    t0 = time.perf_counter()
    r = await _INTERNAL.scan(text)
    return ToolResult(
        ok=True,
        name="scan_internal",
        summary=f"findings={len(r.findings)}",
        data={"findings": [f.model_dump() for f in r.findings], "score": r.score},
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )


async def tool_scan_nhi(text: str, state: ScanState) -> ToolResult:
    t0 = time.perf_counter()
    ctx = {
        "user_id": state.user.user_id,
        "role": state.user.role,
        "resource": state.user.resource,
        "auth_type": state.user.auth_type,
    }
    r = await _NHI.scan(text, **ctx)
    return ToolResult(
        ok=True,
        name="scan_nhi",
        summary=f"findings={len(r.findings)}",
        data={"findings": [f.model_dump() for f in r.findings], "score": r.score},
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )


async def tool_run_full_input_scan(state: ScanState) -> ToolResult:
    """Same 11-scanner battery as legacy ThreatDetectionAgent + borderline judge."""
    t0 = time.perf_counter()
    from app.agents import threat

    await threat.run(state)
    return ToolResult(
        ok=True,
        name="run_full_input_scan",
        summary=f"full_threat findings={len(state.findings)}",
        data={"findings_count": len(state.findings)},
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )


async def tool_memory_recall_similar(text: str, state: ScanState, k: int = 5) -> ToolResult:
    """Episodic recall via pgvector similarity (past BLOCK/ESCALATE requests)."""
    t0 = time.perf_counter()
    from app.agents.memory import episodic

    rows = await episodic.recall_similar_incidents_vector(text, k=k)
    summary = "; ".join(f"{r.get('id')}:{r.get('verdict')} sim={r.get('similarity', 0):.2f}" for r in rows[:k])
    return ToolResult(
        ok=True,
        name="memory_recall_similar",
        summary=summary[:4000] or "no_matches",
        data={"incidents": rows},
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )


async def tool_opa_base(state: ScanState) -> ToolResult:
    t0 = time.perf_counter()
    user = {
        "id": state.user.user_id,
        "tier": state.user.tier,
        "region": state.user.region,
        "historical_risk": state.user.historical_risk,
    }
    d = await _OPA.decide(
        user=user,
        model=state.requested_model,
        verdict=state.verdict.value if hasattr(state.verdict, "value") else str(state.verdict),
        sensitivity=state.sensitivity,
    )
    return ToolResult(
        ok=bool(d.get("allow", True)),
        name="opa_evaluate",
        summary="opa",
        data=d,
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )

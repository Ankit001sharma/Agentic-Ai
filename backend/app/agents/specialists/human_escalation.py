"""HumanEscalationAgent — low-confidence -> brief for HITL."""

from __future__ import annotations

import time

from app.core.config import get_settings
from app.schemas.explanation import AgentFindingRecord
from app.agents.specialists.base import append_finding
from app.agents.tools.base import ToolResult
from app.schemas.sentinel import ScanState, Verdict


async def run(state: ScanState) -> ToolResult:
    t0 = time.perf_counter()
    s = get_settings()
    min_conf = 0.35
    agg = float(state.confidence or state.intent_confidence or 0.0)
    brief = (
        f"user={state.user.user_id} intent={state.intent} risk={state.risk} "
        f"verdict={state.verdict} key_findings={len(state.findings)}"
    )
    if (
        agg < min_conf
        and state.risk > 70
        and state.verdict in (Verdict.ALLOW, Verdict.MASK)
    ):
        state.human_escalation_brief = brief
        state.verdict = Verdict.ESCALATE
    append_finding(
        state,
        AgentFindingRecord(
            agent="human_escalation",
            claim=f"confidence_gate agg={agg:.2f}",
            evidence=[brief[:500]],
            confidence=agg,
            recommended_verdict=state.verdict.value,
        ),
    )
    return ToolResult(
        ok=True,
        name="human_escalation",
        summary=brief[:200],
        data={"brief": brief},
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )

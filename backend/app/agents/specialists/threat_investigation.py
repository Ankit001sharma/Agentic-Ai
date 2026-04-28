"""ThreatInvestigationAgent — targeted scanners + risk signal."""

from __future__ import annotations

import asyncio
import time

from app.agents.tools import security
from app.agents.specialists.base import append_finding
from app.agents.tools.base import ToolResult
from app.core.risk import aggregate
from app.schemas.explanation import AgentFindingRecord
from app.schemas.sentinel import Finding, ScanState


async def run(state: ScanState) -> ToolResult:
    t0 = time.perf_counter()
    text = state.prompt
    results = await asyncio.gather(
        security.tool_scan_injection(text, state),
        security.tool_check_rbac(text, state),
        security.tool_scan_malware(text, state),
        return_exceptions=True,
    )
    for r in results:
        if isinstance(r, Exception):
            continue
        d = r.data or {}
        for f in d.get("findings") or []:
            if isinstance(f, dict):
                state.findings.append(Finding(**f))
    # Optional vector recall
    try:
        vr = await security.tool_recall_vector(text, state)
        for f in (vr.data or {}).get("findings") or []:
            if isinstance(f, dict):
                state.findings.append(Finding(**f))
    except Exception:  # noqa: BLE001
        pass

    rscore, _ = aggregate(state.findings, historical_risk=state.user.historical_risk)
    sev = max((f.severity for f in state.findings), default=0.0)
    append_finding(
        state,
        AgentFindingRecord(
            agent="threat",
            claim=f"prelim_risk~{rscore} max_sev={sev:.2f}",
            evidence=[f"{f.category}:{f.severity:.2f}" for f in state.findings[:8]],
            confidence=float(min(1.0, sev + 0.1)),
            metadata={"findings_count": len(state.findings)},
        ),
    )
    return ToolResult(
        ok=True,
        name="threat",
        summary=f"prelim_risk~{rscore} findings={len(state.findings)}",
        data={"prelim_risk": rscore},
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )

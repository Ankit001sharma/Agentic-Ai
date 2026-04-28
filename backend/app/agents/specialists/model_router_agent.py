"""SmartModelRouterAgent — vLLM-first chain + heuristics."""

from __future__ import annotations

import time

from app.core.config import get_settings
from app.core.task_router import classify_complexity, classify_task, select_model_smart
from app.schemas.explanation import AgentFindingRecord
from app.agents.specialists.base import append_finding
from app.agents.tools.base import ToolResult
from app.schemas.sentinel import ScanState, Verdict


async def run(state: ScanState) -> ToolResult:
    t0 = time.perf_counter()
    s = get_settings()
    if state.verdict == Verdict.BLOCK:
        return ToolResult(
            ok=True,
            name="model_router",
            summary="skipped block",
            data={},
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )
    if not state.task or state.task == "chat":
        state.task = classify_task(state.prompt)
    if not state.complexity or state.complexity == "low":
        state.complexity = classify_complexity(state.prompt)
    chain, primary, audit = select_model_smart(
        tier=state.user.tier,
        requested=state.requested_model,
        sensitivity=state.sensitivity,
        task=state.task,
        complexity=state.complexity,
        allowed=state.allowed_models or None,
    )
    state.selected_model = primary
    state.fallback_chain = list(chain)
    append_finding(
        state,
        AgentFindingRecord(
            agent="model_router",
            claim=f"primary={primary} chain={chain[:3]}",
            evidence=[audit.get("reason", "")],
            confidence=0.75,
            metadata=audit,
        ),
    )
    return ToolResult(
        ok=True,
        name="model_router",
        summary=f"model={primary}",
        data={"primary": primary, "chain": chain, "audit": audit},
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )

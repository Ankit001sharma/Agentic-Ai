"""ModelRoutingAgent — picks the best model + builds fallback chain.

Now task-aware and cost-aware:
    1. classify the prompt's task + complexity (heuristic)
    2. consult the smart routing matrix (sensitive -> local; free tier -> cheap;
       coding/high -> strong model; etc.)
    3. honour OPA allowlist + caller's explicit `model` parameter
"""

from __future__ import annotations

from app.core.task_router import (
    classify_complexity,
    classify_task,
    select_model_smart,
)
from app.schemas.sentinel import ScanState, Verdict


async def run(state: ScanState) -> ScanState:
    if state.verdict == Verdict.BLOCK:
        return state

    # 1. Classify if not already supplied by caller
    if not state.task or state.task == "chat":
        state.task = classify_task(state.prompt)
    if not state.complexity or state.complexity == "low":
        state.complexity = classify_complexity(state.prompt)

    # 2. Smart selection
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
    state.audit_events.append(
        {
            "agent": "model_router",
            "selected": primary,
            "fallback_chain": chain,
            "sensitivity": state.sensitivity,
            "task": state.task,
            "complexity": state.complexity,
            "reason": audit["reason"],
            "chain": chain,
        }
    )
    state.opa_reasons.append(
        f"router task={state.task} complexity={state.complexity} -> {primary}"
    )
    return state

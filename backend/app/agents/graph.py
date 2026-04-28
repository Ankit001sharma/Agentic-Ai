"""Pipeline orchestrator: legacy linear DAG or Sentinel-X agentic path."""

from __future__ import annotations

import datetime as dt
import uuid

from app.agents import (
    adaptive_risk,
    assistant,
    context_builder,
    decision_gate,
    llm_invoke,
    model_router,
    opa_policy,
    output_decision,
    reporting,
    review_queue,
    risk_aggregator,
    sanitizer,
    threat,
    critic,
)
from app.agents.explanation_builder import build_explanation_card
from app.agents import supervisor as supervisor_agent
from app.agents.specialists import (
    human_escalation,
    model_router_agent,
    output_reflection_agent,
    policy as policy_spec,
)
from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.sentinel import ScanState, UserContext, Verdict

log = get_logger("graph")


def _ts() -> float:
    return dt.datetime.now(dt.UTC).timestamp()


async def run_pipeline(
    *,
    user: UserContext,
    prompt: str,
    requested_model: str,
    sensitivity: str = "normal",
) -> ScanState:
    s = get_settings()
    if s.agentic_mode:
        return await run_agentic_pipeline(
            user=user, prompt=prompt, requested_model=requested_model, sensitivity=sensitivity
        )
    return await run_legacy_pipeline(
        user=user, prompt=prompt, requested_model=requested_model, sensitivity=sensitivity
    )


async def run_legacy_pipeline(
    *,
    user: UserContext,
    prompt: str,
    requested_model: str,
    sensitivity: str = "normal",
) -> ScanState:
    state = ScanState(
        request_id=f"req-{uuid.uuid4().hex[:12]}",
        user=user,
        prompt=prompt,
        requested_model=requested_model,
        sensitivity=sensitivity,
        started_at=_ts(),
        agentic_trace_version="1",
    )
    state = await context_builder.run(state)
    state = await threat.run(state)
    state = await risk_aggregator.run(state)
    state = await decision_gate.run(state)
    state = await review_queue.run(state)
    state = await opa_policy.run(state)
    state = await model_router.run(state)
    state = await llm_invoke.run(state)
    if state.verdict != Verdict.BLOCK:
        state = await sanitizer.run(state)
    state = await output_decision.run(state)
    state = await reporting.run(state)
    state = await adaptive_risk.run(state)
    return state


async def run_agentic_pipeline(
    *,
    user: UserContext,
    prompt: str,
    requested_model: str,
    sensitivity: str = "normal",
) -> ScanState:
    s = get_settings()
    state = ScanState(
        request_id=f"req-{uuid.uuid4().hex[:12]}",
        user=user,
        prompt=prompt,
        requested_model=requested_model,
        sensitivity=sensitivity,
        started_at=_ts(),
        agentic_trace_version="2",
    )

    def tr(phase: str, name: str, data: str) -> None:
        state.agent_steps.append(
            {
                "phase": phase,
                "step": len(state.agent_steps),
                "tool": name,
                "observation": data[:2000],
            }
        )

    state = await context_builder.run(state)
    tr("orchestrator", "context", "ok")
    state = await supervisor_agent.run(state)
    tr("specialists", "supervisor", "prescan+nemotron_react_or_legacy")

    state = await risk_aggregator.run(state)
    tr("graph", "risk_aggregator", str(state.risk))
    state = await decision_gate.run(state)
    tr("graph", "decision_gate", str(state.verdict))

    await policy_spec.run(state)
    tr("graph", "policy", str(state.verdict))
    if state.verdict not in (Verdict.BLOCK, Verdict.ESCALATE):
        await model_router_agent.run(state)
        tr("graph", "model_router", str(state.selected_model or ""))
        state = await critic.run(state)
        tr("graph", "critic", "ok")
        await human_escalation.run(state)
        tr("graph", "human_escalation", str(state.verdict))

    if not state.allowed_models:
        from app.core.policies import OPAClient

        u = {
            "id": state.user.user_id,
            "tier": state.user.tier,
            "region": state.user.region,
            "historical_risk": state.user.historical_risk,
        }
        state.allowed_models = await OPAClient().allowed_models(u)

    if state.verdict == Verdict.ESCALATE:
        state = await review_queue.run(state)
        tr("graph", "review_queue", "done")

    n_retries = s.max_output_retries
    if state.verdict in (Verdict.ALLOW, Verdict.MASK):
        for attempt in range(n_retries + 1):
            if attempt > 0 and state.rewrite_constraints:
                c = " ".join(state.rewrite_constraints)
                state = state.model_copy(
                    update={"prompt": (state.prompt or "") + f"\n[constraints: {c}]"},
                    deep=True,
                )
            state = await llm_invoke.run(state)
            if not state.final_response and state.llm_response:
                state = state.model_copy(update={"final_response": state.llm_response}, deep=True)
            state = await output_reflection_agent.run(state)
            v = (state.output_reflection_verdict or "CLEAN").upper()
            if v == "CLEAN" or v == "BLOCK" or attempt >= n_retries:
                if v == "BLOCK" and state.verdict != Verdict.BLOCK:
                    state.final_response = "Response withheld by output policy."
                break
            if v == "REWRITE" and attempt < n_retries:
                state.self_corrections += 1
    elif state.verdict == Verdict.BLOCK:
        state = await llm_invoke.run(state)

    state = await output_decision.run(state)
    state = await assistant.run(state)
    build_explanation_card(state)
    state = await reporting.run(state)
    state = await adaptive_risk.run(state)
    return state

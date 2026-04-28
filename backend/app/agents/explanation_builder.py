"""Build mandatory ExplanationCard payload from ScanState."""

from __future__ import annotations

from app.schemas.explanation import ExplanationCard, PolicyDecisionRecord
from app.schemas.sentinel import ScanState, Verdict


def build_explanation_card(state: ScanState) -> dict[str, object]:
    draft = state.explanation_draft or {}
    v = state.verdict.value if hasattr(state.verdict, "value") else str(state.verdict)
    conf = float(
        draft.get("confidence")
        if draft.get("confidence") is not None
        else (
            state.confidence
            or state.intent_confidence
            or (0.85 if state.risk < 30 else 0.55)
        )
    )
    headline = str(draft.get("headline") or f"Risk {state.risk} → {v}")
    primary = str(draft.get("primary_reason") or state.block_reason or f"aggregated_risk={state.risk}")
    user_msg = str(draft.get("user_facing_message") or _user_msg(state, v, conf))
    steps = (state.agent_steps or [])[-10:]
    alts = [
        "Legacy linear DAG (AGENTIC_MODE=false)",
        "Parallel specialist crew without extra ReAct",
    ]
    if state.self_corrections:
        alts.append(f"Self-correction rounds attempted: {state.self_corrections}")
    card = ExplanationCard(
        verdict=v,
        confidence=conf,
        headline=headline,
        primary_reason=primary,
        contributing_agents=list({a.get("agent", "?") for a in (state.agent_findings or [])}),
        contributing_findings=(state.findings or [])[:8],
        decisive_tool_calls=[dict(s) for s in steps if isinstance(s, dict)],
        intent_classification=state.intent or "unknown",
        policy_decisions=[
            PolicyDecisionRecord(package="opa", allowed=state.opa_allowed, reasons=state.opa_reasons or [])
        ],
        alternatives_considered=alts,
        user_facing_message=user_msg,
    )
    d = card.model_dump()
    state.explanation = d
    return d


def _user_msg(state: ScanState, v: str, _conf: float) -> str:
    if v == "BLOCK":
        return (
            state.block_reason
            or "This request was blocked by SentinelGuard policy or risk thresholds."
        )
    if v == "ESCALATE":
        return "This request is pending human review for safety review."
    return "Request allowed. Response follows."

"""OPAPolicyAgent — invokes Open Policy Agent for the final allow/deny decision."""

from __future__ import annotations

from app.core.logging import get_logger
from app.core.policies import OPAClient
from app.schemas.sentinel import ScanState, Verdict

log = get_logger("agent.opa")

_CLIENT = OPAClient()


async def run(state: ScanState) -> ScanState:
    if state.verdict == Verdict.BLOCK:
        return state  # already decided upstream

    user = {
        "id": state.user.user_id,
        "tier": state.user.tier,
        "region": state.user.region,
        "historical_risk": state.user.historical_risk,
        "role": state.user.role,
    }
    decision = await _CLIENT.decide(
        user=user,
        model=state.requested_model,
        verdict=state.verdict.value,
        sensitivity=state.sensitivity,
    )
    state.opa_allowed = bool(decision.get("allow", True))
    state.opa_reasons = list(decision.get("reasons") or [])

    if not state.opa_allowed:
        state.verdict = Verdict.BLOCK
        state.block_reason = "opa_deny:" + (",".join(state.opa_reasons) or "policy")

    state.allowed_models = await _CLIENT.allowed_models(user)
    state.audit_events.append(
        {
            "agent": "opa",
            "allow": state.opa_allowed,
            "reasons": state.opa_reasons,
            "allowed_models": state.allowed_models,
            "offline": decision.get("_offline", False),
        }
    )
    return state

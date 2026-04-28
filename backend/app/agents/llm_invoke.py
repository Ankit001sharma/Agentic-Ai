"""LLMInvocationAgent — calls upstream LLM with the fallback chain
produced by ModelRoutingAgent (task + complexity + cost + tier + sensitivity
+ OPA-allowlist aware).

If the router did not populate `state.fallback_chain` (defensive: e.g. a
future code path bypasses the router), we fall back to the legacy
tier+sensitivity-only selector so the call still has a chance to succeed.
"""

from __future__ import annotations

from app.core.routing_matrix import select_model
from app.llm.litellm_client import acomplete
from app.schemas.sentinel import ScanState, Verdict


async def run(state: ScanState) -> ScanState:
    if state.verdict == Verdict.BLOCK:
        # Provide canned safe refusal so the response can flow through output pipeline
        state.llm_response = (
            "I can't help with that request because it appears to violate our safety policy."
        )
        return state

    prompt_text = state.redacted_prompt or state.prompt

    chain = list(state.fallback_chain or [])
    chain_source = "router_smart_chain"
    if not chain:
        chain, _ = select_model(
            tier=state.user.tier,
            requested=state.selected_model or state.requested_model,
            sensitivity=state.sensitivity,
            allowed=state.allowed_models or None,
        )
        chain_source = "legacy_tier_chain"

    text, model_used, fallback = await acomplete(
        messages=[{"role": "user", "content": prompt_text}],
        fallback_chain=chain,
    )
    state.llm_response = text
    state.selected_model = model_used
    state.fallback_used = fallback
    state.audit_events.append(
        {
            "agent": "llm_invoke",
            "model_used": model_used,
            "fallback": fallback,
            "chain": chain,
            "chain_source": chain_source,
        }
    )
    return state

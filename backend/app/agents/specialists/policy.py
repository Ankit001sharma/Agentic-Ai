"""PolicyAgent — OPA layers + contextual LLM nuance (when configured)."""

from __future__ import annotations

import json
import time

from app.core.config import get_settings
from app.core.policies import OPAClient
from app.llm.litellm_client import acomplete, _vllm_litellm_model
from app.schemas.explanation import AgentFindingRecord, PolicyDecisionRecord
from app.agents.specialists.base import append_finding
from app.agents.tools.base import ToolResult
from app.schemas.sentinel import ScanState, Verdict
from app.core.risk import to_verdict

_OPA = OPAClient()


async def _llm_contextual_nuance(
    state: ScanState,
    ir: dict,
    acc: dict,
    comp: dict,
) -> None:
    """When OPA signals human review and no hard malware deny — refine verdict with vLLM."""
    s = get_settings()
    if not s.vllm_base_url:
        return
    if ir.get("deny_outright"):
        return
    if state.verdict == Verdict.BLOCK:
        return
    cats = {str(f.category).upper() for f in state.findings}
    if any(x in cats for x in ("MALWARE", "EXPLOIT", "RANSOMWARE")):
        return
    if not ir.get("require_human_review"):
        return
    m = _vllm_litellm_model(s.vllm_planner_model)
    payload = {
        "intent_rules": ir,
        "access_allow": acc.get("allow"),
        "compliance_allow": comp.get("allow"),
        "risk": state.risk,
        "intent": state.intent,
        "findings": [f"{f.category}:{f.severity:.2f}" for f in state.findings[:16]],
    }
    prompt = (
        "Interpret combined policy signals with organizational nuance (not threshold-only). "
        'Reply JSON only: {"aligned_verdict":"ALLOW|MASK|ESCALATE|BLOCK",'
        '"rationale":"one sentence","confidence":0.0-1.0}. '
        "Use ESCALATE when intent/access signals conflict or ambiguity is high.\n\n"
        + json.dumps(payload, default=str)[:6000]
    )
    text, _, _ = await acomplete([{"role": "user", "content": prompt}], fallback_chain=[m])
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[-1]
        if raw.lower().startswith("json"):
            raw = raw[4:].lstrip()
    try:
        d = json.loads(raw) if raw.startswith("{") else {}
        av = str(d.get("aligned_verdict", "")).upper()
        rationale = str(d.get("rationale", ""))[:500]
        conf = float(d.get("confidence", 0.5))
        if av == "ESCALATE" and state.verdict != Verdict.BLOCK:
            state.verdict = Verdict.ESCALATE
            state.block_reason = (state.block_reason or "") + "|policy_llm_escalate"
        elif av == "BLOCK" and state.verdict != Verdict.BLOCK:
            state.verdict = Verdict.BLOCK
            state.block_reason = (state.block_reason or "") + "|policy_llm_block"
        state.confidence = min(0.99, max(state.confidence, conf))
        append_finding(
            state,
            AgentFindingRecord(
                agent="policy",
                claim="contextual_policy_llm",
                evidence=[rationale or av],
                confidence=conf,
                metadata={"aligned_verdict": av},
            ),
        )
    except Exception:  # noqa: BLE001
        pass


async def run(state: ScanState) -> ToolResult:
    t0 = time.perf_counter()
    if state.verdict == Verdict.BLOCK:
        return ToolResult(
            ok=True,
            name="policy",
            summary="skip_already_blocked",
            data={},
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )
    user = {
        "id": state.user.user_id,
        "tier": state.user.tier,
        "region": state.user.region,
        "historical_risk": state.user.historical_risk,
        "role": state.user.role,
    }
    base_v = to_verdict(state.risk)
    d = await _OPA.decide(
        user=user,
        model=state.requested_model,
        verdict=base_v.value,
        sensitivity=state.sensitivity,
    )
    state.opa_allowed = bool(d.get("allow", True))
    state.opa_reasons = list(d.get("reasons") or [])

    intent = state.intent or "general_chat"
    acc = await _OPA.decide_access(
        user=user,
        resource=state.user.resource,
        action="read",
        intent=intent,
    )
    comp = await _OPA.decide_compliance(user, "NONE", {})
    ir = await _OPA.decide_intent_rules(user, intent, state.sensitivity)

    recs: list[PolicyDecisionRecord] = [
        PolicyDecisionRecord(package="sentinel", allowed=state.opa_allowed, reasons=state.opa_reasons),
        PolicyDecisionRecord(
            package="access", allowed=acc.get("allow", True), reasons=list(acc.get("reasons") or [])
        ),
        PolicyDecisionRecord(
            package="compliance",
            allowed=comp.get("allow", True),
            reasons=list(comp.get("reasons") or []),
        ),
    ]
    if not state.opa_allowed or not acc.get("allow", True) or not comp.get("allow", True):
        state.verdict = Verdict.BLOCK
        state.block_reason = "policy_deny"
    if ir.get("deny_outright"):
        state.verdict = Verdict.BLOCK
        state.block_reason = (state.block_reason or "policy") + "|intent_deny_outright"
    if ir.get("require_human_review") and state.verdict != Verdict.BLOCK:
        state.verdict = Verdict.ESCALATE

    state.allowed_models = await _OPA.allowed_models(user)
    state.confidence = min(
        0.99,
        float(state.intent_confidence) * 0.6
        + (0.3 if state.opa_allowed and acc.get("allow") else 0.0)
        + (0.1 if not state.findings else 0.0),
    )

    await _llm_contextual_nuance(state, ir, acc, comp)

    append_finding(
        state,
        AgentFindingRecord(
            agent="policy",
            claim=f"verdict={state.verdict} opa={state.opa_allowed} access={acc.get('allow')}",
            evidence=state.opa_reasons,
            confidence=0.9,
            recommended_verdict=str(
                state.verdict.value if hasattr(state.verdict, "value") else state.verdict
            ),
            metadata={"intent_rules": ir, "policies": [p.model_dump() for p in recs]},
        ),
    )
    return ToolResult(
        ok=True,
        name="policy",
        summary=f"verdict={state.verdict} opa={state.opa_allowed}",
        data={"verdict": state.verdict.value, "opa": d, "access": acc, "intent_rules": ir},
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )

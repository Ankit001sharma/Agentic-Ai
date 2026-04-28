"""CriticAgent / Reflexion — replan up to N times via plan_hint."""

from __future__ import annotations

import json

from app.core.config import get_settings
from app.llm.litellm_client import acomplete, _vllm_litellm_model
from app.schemas.sentinel import ScanState, Verdict


async def run(state: ScanState, ref_budget: int | None = None) -> ScanState:
    s = get_settings()
    n = ref_budget if ref_budget is not None else s.max_reflections
    if n <= 0:
        return state
    m = _vllm_litellm_model(s.vllm_critic_model)
    payload = {
        "findings": [a.get("claim") for a in state.agent_findings[:20]],
        "verdict": state.verdict.value,
        "risk": state.risk,
        "prompt_preview": (state.prompt or "")[:2000],
    }
    system = (
        "You are a security review critic. Given agent findings and a proposed verdict, "
        "reply with JSON: {\"verdict_consistent\": true/false, \"suggested_action\": "
        "\"approve\"|\"replan\", \"notes\": \"...\"}."
    )
    text, _, _ = await acomplete(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(payload)[:12000]},
        ],
        fallback_chain=[m] if s.vllm_base_url else [s.default_model],
    )
    ok = True
    try:
        t = (text or "").strip()
        if t.startswith("```"):
            t = t.split("```", 2)[-1]
            if t.lower().startswith("json"):
                t = t[4:].lstrip()
        d = json.loads(t) if t.startswith("{") else {"verdict_consistent": True}
        ok = bool(d.get("verdict_consistent", True))
        if not ok and d.get("suggested_action") == "replan" and d.get("notes"):
            state.plan_hint = str(d.get("notes"))[:2000]
    except Exception:  # noqa: BLE001
        pass
    state.reflections.append(
        {
            "verdict_consistent": ok,
            "plan_hint": state.plan_hint,
        }
    )
    return state

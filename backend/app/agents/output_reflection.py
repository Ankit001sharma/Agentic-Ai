"""OutputReflectionAgent — post-LLM review; emit rewrite constraints."""

from __future__ import annotations

import json

from app.core.config import get_settings
from app.llm.litellm_client import acomplete, _vllm_litellm_model
from app.agents import sanitizer
from app.schemas.sentinel import OutputVerdict, ScanState, Verdict


async def run(state: ScanState) -> ScanState:
    s = get_settings()
    if state.verdict == Verdict.BLOCK:
        return state
    text = state.final_response or state.llm_response or ""
    if not text.strip():
        return state
    state.llm_response = text
    state = await sanitizer.run(state)
    if state.output_findings:
        state.rewrite_constraints = [f"{f.category}:{f.scanner}" for f in state.output_findings[:5]]

    m = _vllm_litellm_model(s.vllm_critic_model)
    crit = (
        "Classify assistant output. Reply JSON only: "
        '{"verdict":"CLEAN|REWRITE|BLOCK","issues":[],"rewrite_constraints":[]}\n\n'
        f"Text:\n{text[:4000]}"
    )
    t, _, _ = await acomplete(
        [{"role": "user", "content": crit}],
        fallback_chain=[m] if s.vllm_base_url else [s.default_model],
    )
    v = "CLEAN"
    try:
        raw = (t or "").strip()
        if raw.startswith("```"):
            raw = raw.split("```", 2)[-1]
        d = json.loads(raw) if raw.startswith("{") else {}
        v = str(d.get("verdict", "CLEAN")).upper()
        for c in d.get("rewrite_constraints") or []:
            if c and c not in state.rewrite_constraints:
                state.rewrite_constraints.append(str(c))
    except Exception:  # noqa: BLE001
        v = "REWRITE" if state.output_findings else "CLEAN"
    state.output_reflection_verdict = v
    if v == "BLOCK":
        state.output_verdict = OutputVerdict.BLOCK
    elif v == "REWRITE":
        state.output_verdict = OutputVerdict.REDACT
    else:
        state.output_verdict = OutputVerdict.CLEAN
    return state

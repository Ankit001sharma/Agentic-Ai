"""Helpers for specialist agents."""

from __future__ import annotations

import json
from typing import Any

from app.core.config import get_settings
from app.llm.litellm_client import acomplete, _vllm_litellm_model
from app.schemas.explanation import AgentFindingRecord
from app.schemas.sentinel import ScanState

_INTENT_SYSTEM = (
    "You classify user intent for a security LLM gateway. "
    "Reply with JSON only: "
    '{"intent": "<one of: general_chat,data_extraction,privilege_escalation,'
    'code_generation,compliance_question,credential_request,policy_override_request,'
    'jailbreak_attempt,internal_q_and_a,creative,other>", '
    '"sub_intent": "short phrase", "confidence": 0.0-1.0, "evidence": "brief"}'
)


async def classify_intent_json(prompt: str) -> dict[str, Any]:
    s = get_settings()
    m = _vllm_litellm_model(s.vllm_planner_model)
    text, model, _ = await acomplete(
        [
            {"role": "system", "content": _INTENT_SYSTEM},
            {"role": "user", "content": (prompt or "")[:8000]},
        ],
        fallback_chain=[m] if s.vllm_base_url else [s.default_model],
    )
    try:
        t = (text or "").strip()
        if t.startswith("```"):
            t = t.split("```", 2)[-1]
            if t.lower().startswith("json"):
                t = t[4:].lstrip()
        return json.loads(t) if t.startswith("{") else {"intent": "general_chat", "sub_intent": t[:80], "confidence": 0.3, "evidence": t[:200]}
    except Exception:  # noqa: BLE001
        return {"intent": "general_chat", "sub_intent": "", "confidence": 0.0, "evidence": "parse_error"}


def append_finding(state: ScanState, rec: AgentFindingRecord) -> None:
    state.agent_findings.append(
        {
            "agent": rec.agent,
            "claim": rec.claim,
            "evidence": rec.evidence,
            "confidence": rec.confidence,
            "recommended_verdict": rec.recommended_verdict,
            "recommended_action": rec.recommended_action,
            "metadata": rec.metadata,
        }
    )

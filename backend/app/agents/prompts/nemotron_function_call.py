"""Stage 8 — Nemotron function-call prompt builder."""

from __future__ import annotations

import json
from typing import Any


_SYSTEM = """\
You are a precise function-call argument generator for an AI security gateway.
Given a verified user intent, extracted entities, and a tool's JSON schema,
produce the exact arguments needed to call that tool.

Return ONLY valid JSON — no markdown, no extra text — matching this schema:
{
  "tool_id": "<tool_id>",
  "arguments": { /* all required fields + relevant optional fields */ },
  "idempotency_key": "<short unique string based on the request>",
  "rationale": "<one sentence explaining the argument choices>",
  "missing_required_fields": ["field1", "field2"]
}

Rules:
- Populate every required field from entities, memory, or reasonable inference.
- List any required field you cannot populate in missing_required_fields.
- Set simulate=true in arguments only if the caller already set it.
- Do NOT invent data that isn't present or inferable from the prompt/context.
- idempotency_key should be a short deterministic string (e.g. first 12 chars of a hash of key fields).
"""


def _serialize_entities(entities: Any) -> str:
    """Safely serialize entities to a JSON string regardless of input type."""
    if entities is None:
        return "[]"
    # Pydantic BaseModel (IntentEntities)
    if hasattr(entities, "model_dump"):
        return json.dumps(entities.model_dump(), ensure_ascii=False)
    # Plain list or dict
    try:
        return json.dumps(entities, ensure_ascii=False)
    except (TypeError, ValueError):
        return json.dumps(str(entities))


def _format_stm_history(stm_context: Any) -> str:
    """Format STM context (dict or str) into a readable history block."""
    if not stm_context:
        return ""
    if isinstance(stm_context, dict):
        past_msgs = stm_context.get("messages", [])
        if not past_msgs:
            return ""
        lines: list[str] = []
        for msg in past_msgs[-4:]:
            role = str(msg.get("role", "user"))
            content = str(msg.get("content", ""))[:200]
            lines.append(f"{role}: {content}")
        return "\n\n## Conversation history\n" + "\n".join(lines)
    if isinstance(stm_context, str) and stm_context.strip():
        return f"\n\n## Conversation history\n{stm_context}"
    return ""


def build_messages(
    *,
    tool_id: str,
    tool_description: str,
    intent: str,
    intent_description: str = "",
    entities: Any = None,
    tool_schema: dict[str, Any] | None = None,
    simulate: bool = False,
    user_prompt: str = "",
    stm_context: Any = None,
    user_id: str = "",
    role: str = "",
    timezone: str | None = None,
    language: str | None = None,
    default_signature: str | None = None,
) -> list[dict[str, Any]]:
    schema_str = json.dumps(tool_schema or {}, indent=2)
    entity_str = _serialize_entities(entities)

    context_parts: list[str] = []
    if user_id:
        context_parts.append(f"user_id: {user_id}")
    if role:
        context_parts.append(f"role: {role}")
    if timezone:
        context_parts.append(f"timezone: {timezone}")
    if language:
        context_parts.append(f"language: {language}")
    if default_signature:
        context_parts.append(f"default_signature: {default_signature}")
    if simulate:
        context_parts.append("simulate: true (dry-run — do not perform real side effects)")

    user_ctx = "\n".join(context_parts)
    history_block = _format_stm_history(stm_context)

    user_content = (
        f"## Tool to call\n"
        f"tool_id: {tool_id}\n"
        f"description: {tool_description}\n\n"
        f"## Tool JSON schema\n{schema_str}\n\n"
        f"## User intent\n{intent}"
        + (f"\n{intent_description}" if intent_description else "")
        + f"\n\n## Extracted entities\n{entity_str}\n\n"
        f"## User prompt\n{user_prompt}"
        f"{history_block}"
        + (f"\n\n## Caller context\n{user_ctx}" if user_ctx else "")
    )

    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user_content},
    ]

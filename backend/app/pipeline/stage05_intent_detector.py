"""Stage 5 — Mistral Intent Detector (LLM #1).

Classifies the user prompt into a structured IntentResult:
  - intent type (send_email, create_ticket, search_documents, …)
  - rich entities (people with email, orgs, dates, ids, urls, raw_values)
  - tool_id mapping
  - confidence + ambiguity flag
  - memory_references_resolved (pronoun resolution audit trail)

Reads STM context for pronoun resolution.
Writes intent + flat entity list back to STM after successful parse.
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from app.agents.prompts.mistral_intent import build_messages
from app.core.config import get_settings
from app.core.logging import get_logger
from app.llm.litellm_client import acomplete_intent_fast
from app.memory.stm import ShortTermMemory
from app.pipeline.base import Stage
from app.schemas.sentinel import IntentEntities, IntentResult, PersonEntity, ScanState, Verdict
from app.tools.registry import get_tool_definition, list_tool_ids

log = get_logger("pipeline.stage05")


class IntentDetectorStage(Stage):
    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._stm = ShortTermMemory(redis_client)

    async def run(self, state: ScanState) -> ScanState:
        state.pipeline_stage = 5
        s = get_settings()

        # Short-circuit if already blocked
        if state.verdict == Verdict.BLOCK:
            return state

        tool_ids = list_tool_ids()
        tool_descriptions = {
            tid: (get_tool_definition(tid) or {}).get("description", "")
            for tid in tool_ids
        }

        messages = build_messages(
            prompt=state.prompt,
            tool_ids=tool_ids,
            stm_context=state.stm_context,
            tool_descriptions=tool_descriptions,
        )

        # Stage 5 intent LLM. Routing precedence is handled by ``acomplete_intent_fast``:
        #   1. MISTRAL_API_KEY    → Mistral cloud (LiteLLM ``mistral/<model>``).
        #   2. VLLM_INTENT_MODEL  → vLLM (LiteLLM ``openai/<served_name>`` + ``/v1``).
        #   3. VLLM_PLANNER_MODEL → same vLLM endpoint as #2.
        # The helper also normalizes ``api_base`` and provider prefix, so we don't
        # call ``litellm.acompletion`` directly here (which previously failed with
        # "LLM Provider NOT provided" against a Nemotron-only vLLM server).

        try:
            raw, model_used, _ = await acomplete_intent_fast(messages)

            result = _parse_intent_result(raw)
            _populate_state(state, result)

            log.info(
                "stage05_done",
                request_id=state.request_id,
                model=model_used,
                intent=state.intent,
                tool_id=state.tool_id,
                confidence=state.intent_confidence,
                ambiguous=state.intent_ambiguous,
                resolved=state.memory_references_resolved,
            )

            # Persist intent + flat entity list to STM
            if state.user.user_id != "anonymous":
                flat_entities = _flatten_entities(result.entities)
                await self._stm.update_intent(
                    state.user.user_id,
                    state.conv_id,
                    result.intent,
                    flat_entities,
                )

        except Exception as exc:  # noqa: BLE001
            log.warning("stage05_llm_error", error=str(exc), request_id=state.request_id)
            # Degrade gracefully — pipeline continues without tool mapping
            state.intent = None
            state.tool_id = None
            state.intent_result = None
            state.pipeline_error = {
                "code": "INTENT_LLM_FAILED",
                "message": str(exc)[:500],
                "retryable": True,
                "user_facing": True,
                "stage": "stage05_intent",
            }

        return state


# ── helpers ──────────────────────────────────────────────────────────────────

def _parse_intent_result(raw: str) -> IntentResult:
    """Extract and validate the JSON object from the LLM response."""
    text = raw.strip()

    # Strip accidental markdown fences the model may emit despite instructions
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(l for l in lines if not l.strip().startswith("```"))
    text = text.strip()

    # Try full parse
    data: dict[str, Any] = {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Find first { ... } block
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                data = json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

    if not data:
        return IntentResult(intent="NONE", ambiguous=True)

    # Coerce entities sub-object
    raw_entities = data.get("entities", {})
    people = [
        PersonEntity(
            name=p.get("name", ""),
            email=p.get("email"),
            resolved_from_memory=bool(p.get("resolved_from_memory", False)),
        )
        for p in raw_entities.get("people", [])
        if isinstance(p, dict) and p.get("name")
    ]
    entities = IntentEntities(
        people=people,
        organizations=_coerce_str_list(raw_entities.get("organizations", [])),
        dates=_coerce_str_list(raw_entities.get("dates", [])),
        ids=_coerce_str_list(raw_entities.get("ids", [])),
        urls=_coerce_str_list(raw_entities.get("urls", [])),
        raw_values=raw_entities.get("raw_values", {}),
    )

    tool_id_raw = data.get("tool_id")
    if isinstance(tool_id_raw, str) and tool_id_raw and tool_id_raw != "NONE":
        tool_id: str | None = tool_id_raw
    else:
        tool_id = None

    # Coerce memory_references_resolved into a list[str] — the LLM occasionally
    # returns a string or dict, which would crash IntentResult validation and
    # then get swallowed by the broad except in run().
    mem_refs_raw = data.get("memory_references_resolved", [])
    if isinstance(mem_refs_raw, list):
        memory_references_resolved = [str(x) for x in mem_refs_raw if x is not None]
    elif isinstance(mem_refs_raw, str) and mem_refs_raw.strip():
        memory_references_resolved = [mem_refs_raw.strip()]
    else:
        memory_references_resolved = []

    return IntentResult(
        intent=str(data.get("intent", "NONE")),
        entities=entities,
        tool_id=tool_id,
        confidence=float(data.get("confidence", 0.0)),
        ambiguous=bool(data.get("ambiguous", False)),
        clarification_needed=data.get("clarification_needed"),
        memory_references_resolved=memory_references_resolved,
    )


def _populate_state(state: ScanState, result: IntentResult) -> None:
    """Write the IntentResult fields into the ScanState."""
    state.intent_result = result
    state.intent = result.intent if result.intent != "NONE" else None
    state.tool_id = result.tool_id
    state.intent_confidence = result.confidence
    state.intent_ambiguous = result.ambiguous
    state.intent_clarification = result.clarification_needed
    state.memory_references_resolved = result.memory_references_resolved

    # Backward-compat flat list: names + emails + orgs + raw values
    state.intent_entities = _flatten_entities(result.entities)


def _coerce_str_list(raw: list) -> list[str]:
    """Coerce a list that may contain dicts (LLM hallucination) into plain strings."""
    out: list[str] = []
    for item in raw:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            # Prefer common name-like keys, fall back to first value, then JSON
            for key in ("name", "value", "text", "label"):
                if key in item and isinstance(item[key], str):
                    out.append(item[key])
                    break
            else:
                # Use first string value found, else skip
                first = next((str(v) for v in item.values() if v), None)
                if first:
                    out.append(first)
        elif item is not None:
            out.append(str(item))
    return out


def _flatten_entities(entities: IntentEntities) -> list[str]:
    """Produce a flat string list for STM storage and backward-compat code."""
    flat: list[str] = []
    for p in entities.people:
        flat.append(p.email if p.email else p.name)
    flat.extend(entities.organizations)
    flat.extend(entities.dates)
    flat.extend(entities.ids)
    flat.extend(entities.urls)
    flat.extend(str(v) for v in entities.raw_values.values())
    return flat

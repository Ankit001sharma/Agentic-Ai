"""Stage 8 — Nemotron Function Call (LLM #2).

Generates schema-valid tool arguments from the verified intent and entities.
Parses the full FunctionCallResult contract including:
  - arguments     → tool_args on state
  - rationale     → tool_args_rationale on state
  - missing_required_fields → state.missing_required_fields (blocks execution)
  - external: true in args  → state.fn_call_external = True (triggers Stage 10)
  - requires_confirmation: true → state.fn_call_requires_confirmation = True (triggers Stage 10)

Security note: the LLM-proposed idempotency_key is stored for audit only.
Stage 11 always uses state.idempotency_key (generated at request creation time).
"""

from __future__ import annotations

import json
from typing import Any

from app.agents.prompts.nemotron_function_call import build_messages
from app.core.config import get_settings
from app.core.logging import get_logger
from app.llm.litellm_client import _provider_kwargs, _vllm_litellm_model
from app.pipeline.base import Stage
from app.schemas.sentinel import FunctionCallResult, ScanState, Verdict
from app.tools.registry import get_tool_definition

log = get_logger("pipeline.stage08")


class NemotronFunctionCallStage(Stage):
    async def run(self, state: ScanState) -> ScanState:
        state.pipeline_stage = 8
        s = get_settings()

        if not state.tool_id or not state.tool_schema:
            return state
        if state.verdict == Verdict.BLOCK:
            return state

        tool_def = state.tool_definition or get_tool_definition(state.tool_id) or {}
        entities = (
            state.intent_result.entities
            if state.intent_result is not None
            else state.intent_entities
        )

        messages = build_messages(
            tool_id=state.tool_id,
            tool_description=tool_def.get("description", ""),
            intent=state.intent or "",
            intent_description="",
            entities=entities,
            tool_schema=state.tool_schema,
            simulate=state.simulate,
            # Extra context injected per spec
            user_prompt=state.prompt,
            stm_context=state.stm_context,
            user_id=state.user.user_id,
            role=state.user.role,
            timezone=state.user.timezone,
            language=state.user.language,
            default_signature=state.user.default_signature,
        )

        # Model resolution priority:
        #   1. Groq (when GROQ_API_KEY is set) — primary for function calls
        #   2. NEMOTRON_MODEL / vLLM — fallback when Groq is unavailable
        if s.groq_api_key and s.groq_model:
            raw_model = s.groq_model
        else:
            raw_model = (s.nemotron_model or "").strip() or s.vllm_planner_model or s.vllm_judge_model
        if not raw_model:
            log.warning("stage08_no_model", request_id=state.request_id)
            return state

        litellm_model = _vllm_litellm_model(raw_model)
        extra = _provider_kwargs(litellm_model)

        try:
            import litellm  # type: ignore[import]

            kwargs: dict[str, Any] = {
                "model": litellm_model,
                "messages": messages,
                "max_tokens": s.nemotron_max_tokens,
                "temperature": 0.0,
                "timeout": s.nemotron_timeout,
                **extra,
            }

            if s.langfuse_enabled:
                _attach_langfuse(kwargs, state.request_id, "stage08_nemotron_fn_call")

            response = await litellm.acompletion(**kwargs)
            raw = response.choices[0].message.content or ""

            fc_result = _parse_fn_call_result(raw, expected_tool_id=state.tool_id)
            _populate_state(state, fc_result)

            log.info(
                "stage08_done",
                request_id=state.request_id,
                tool_id=state.tool_id,
                args_keys=list(state.tool_args.keys()),
                missing=state.missing_required_fields,
                external=state.fn_call_external,
                requires_confirmation=state.fn_call_requires_confirmation,
            )

        except Exception as exc:  # noqa: BLE001
            log.warning("stage08_llm_error", error=str(exc), request_id=state.request_id)
            state.tool_args = {}
            state.fn_call_result = None
            # Surface the failure as a structured pipeline_error so operators
            # can distinguish "no tool needed" from "Nemotron crashed". Mirrors
            # Stage 5's pattern.
            state.pipeline_error = {
                "code": "FUNCTION_CALL_LLM_FAILED",
                "message": str(exc)[:500],
                "retryable": True,
                "user_facing": True,
                "stage": "stage08_nemotron_fn_call",
            }

        return state


# ── parsing ───────────────────────────────────────────────────────────────────

def _parse_fn_call_result(raw: str, expected_tool_id: str) -> FunctionCallResult:
    """Validate and coerce the LLM's JSON output into a FunctionCallResult."""
    text = raw.strip()
    # Strip accidental markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(l for l in lines if not l.strip().startswith("```"))
    text = text.strip()

    data: dict[str, Any] = {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                data = json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

    if not data:
        return FunctionCallResult(tool_id=expected_tool_id)

    # Guarantee tool_id matches what we sent
    tool_id = str(data.get("tool_id") or expected_tool_id)
    if tool_id != expected_tool_id:
        log.warning(
            "stage08_tool_id_mismatch",
            llm_tool_id=tool_id,
            expected=expected_tool_id,
        )
        tool_id = expected_tool_id

    arguments = data.get("arguments") or {}
    if not isinstance(arguments, dict):
        arguments = {}

    missing = data.get("missing_required_fields") or []
    if not isinstance(missing, list):
        missing = []

    return FunctionCallResult(
        tool_id=tool_id,
        arguments=arguments,
        idempotency_key=str(data.get("idempotency_key") or ""),
        rationale=str(data.get("rationale") or ""),
        missing_required_fields=[str(f) for f in missing],
    )


# ── state population ──────────────────────────────────────────────────────────

def _populate_state(state: ScanState, result: FunctionCallResult) -> None:
    """Write FunctionCallResult into the ScanState."""
    state.fn_call_result = result
    state.tool_args_rationale = result.rationale

    args = dict(result.arguments)

    # Always inject simulate flag from the request — LLM must not override this
    if state.simulate:
        args["simulate"] = True

    # Robust fallback: if the tool schema requires a query-like field and the
    # LLM omitted it, reuse the original user prompt as the search text.
    required_fields = [
        str(f)
        for f in ((state.tool_schema or {}).get("required") or [])
        if isinstance(f, str)
    ]
    prompt_fallback_fields = {"query", "prompt", "question", "text"}
    for field in required_fields:
        if field in prompt_fallback_fields:
            val = args.get(field)
            if not isinstance(val, str) or not val.strip():
                if state.prompt.strip():
                    args[field] = state.prompt.strip()

    missing_required_fields = list(result.missing_required_fields)
    for field in required_fields:
        val = args.get(field)
        is_missing = val is None
        if isinstance(val, str):
            is_missing = is_missing or not val.strip()
        elif isinstance(val, list):
            is_missing = is_missing or len(val) == 0
        elif isinstance(val, dict):
            is_missing = is_missing or len(val) == 0
        if is_missing and field not in missing_required_fields:
            missing_required_fields.append(field)
    state.missing_required_fields = missing_required_fields

    state.tool_args = args

    # Detect flags that promote this call to high-impact
    state.fn_call_external = bool(args.get("external"))
    state.fn_call_requires_confirmation = bool(args.get("requires_confirmation"))

    # Propagate to stage.high_impact so Stage 10 triggers
    if state.fn_call_external or state.fn_call_requires_confirmation:
        state.high_impact = True


# ── Langfuse ──────────────────────────────────────────────────────────────────

def _attach_langfuse(kwargs: dict, request_id: str, name: str) -> None:
    try:
        from langfuse import Langfuse  # type: ignore[import]
        from app.core.config import get_settings
        s = get_settings()
        lf = Langfuse(
            public_key=s.langfuse_public_key,
            secret_key=s.langfuse_secret_key,
            host=s.langfuse_host,
        )
        trace = lf.trace(name=name, id=request_id)
        kwargs["metadata"] = {"langfuse_trace_id": trace.id}
    except Exception:  # noqa: BLE001
        pass

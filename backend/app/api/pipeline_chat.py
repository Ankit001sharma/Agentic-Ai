"""POST /chat — 14-stage agentic execution pipeline endpoint.

Request:  { "prompt": str, "conv_id"?: str, "model_pref"?: str, "simulate"?: bool }
Response: 200 { request_id, conv_id, verdict, risk, intent, tool_id,
                tool_executed, simulated, result, message, latency_ms, ... }
          4xx { code, message, retryable, user_facing, sentinel: {...} }
"""

from __future__ import annotations

import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.deps import get_user_context, require_api_key
from app.core.logging import get_logger
from app.pipeline.runner import run_pipeline
from app.pipeline.stage14_response import build_response_payload
from app.schemas.sentinel import UserContext, Verdict

log = get_logger("api.pipeline_chat")

router = APIRouter()


# region agent log
def _debug_log(run_id: str, hypothesis_id: str, location: str, message: str, data: dict) -> None:
    try:
        payload = {
            "sessionId": "caa63e",
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with open("debug-caa63e.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
# endregion


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=32_000)
    conv_id: str | None = Field(default=None, description="Conversation ID for STM continuity")
    model_pref: str | None = Field(default=None, description="Optional preferred model")
    simulate: bool = Field(default=False, description="Dry-run tool execution (no real side effects)")


class ChatResponse(BaseModel):
    request_id: str
    conv_id: str
    verdict: str
    risk: int
    intent: str | None
    intent_detail: dict | None = None       # Stage 5: full IntentResult
    fn_call_detail: dict | None = None      # Stage 8: FunctionCallResult metadata
    tool_id: str | None
    tool_executed: bool
    simulated: bool
    result: dict | None
    message: str
    latency_ms: int
    findings_count: int
    # Use Field(default_factory=...) for mutable defaults — bare `[]` would
    # be shared across all model instances.
    missing_required_fields: list[str] = Field(default_factory=list)
    pipeline_error: dict | None = None
    agent_steps: list = Field(default_factory=list)
    output_verdict: str = "CLEAN"
    output_risk: int = 0


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    _: str = Depends(require_api_key),
    user: UserContext = Depends(get_user_context),
) -> ChatResponse:
    """Execute a user prompt through the full 14-stage pipeline."""

    # Resolve or create a conversation ID for STM continuity
    conv_id = body.conv_id or uuid.uuid4().hex[:16]
    # region agent log
    _debug_log(
        f"api-{conv_id}",
        "H1",
        "pipeline_chat.py:chat:entry",
        "pipeline chat endpoint entry",
        {
            "prompt_len": len(body.prompt or ""),
            "simulate": bool(body.simulate),
            "has_conv_id": bool(body.conv_id),
            "code_version": "pipeline-chat-debug-v1",
        },
    )
    # endregion

    log.info(
        "chat_v2_recv",
        user_id=user.user_id,
        tier=user.tier,
        conv_id=conv_id,
        simulate=body.simulate,
        prompt_chars=len(body.prompt or ""),
        prompt_preview=(body.prompt or "")[:120],
    )

    # Retrieve the shared Redis client from app state (set at startup)
    redis_client = request.app.state.redis

    state = await run_pipeline(
        prompt=body.prompt,
        user=user,
        conv_id=conv_id,
        redis_client=redis_client,
        simulate=body.simulate,
        requested_model=body.model_pref or "default",
    )

    payload = build_response_payload(state)
    log.info(
        "chat_v2_done",
        request_id=state.request_id,
        conv_id=conv_id,
        verdict=state.verdict.value,
        risk=state.risk,
        intent=state.intent,
        tool_id=state.tool_id,
        tool_executed=state.tool_executed,
        latency_ms=state.latency_ms,
    )

    # OPA policy denial → 200 "not permitted" (diagram: "Policy Denial Reply")
    if state.policy_denied:
        return ChatResponse(**payload)

    if state.verdict == Verdict.BLOCK:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "REQUEST_BLOCKED",
                "message": state.block_reason or "Request blocked by security policy",
                "retryable": False,
                "user_facing": True,
                "sentinel": payload,
            },
        )

    if state.pipeline_error and not state.tool_executed and state.tool_id:
        err = state.pipeline_error
        status_code = 422 if not err.get("retryable") else 503
        raise HTTPException(
            status_code=status_code,
            detail={
                **err,
                "sentinel": payload,
            },
        )

    return ChatResponse(**payload)

"""OpenAI Chat Completions-compatible endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Header, Request

from app.agents.graph import run_pipeline
from app.api.deps import get_user_context, require_api_key
from app.schemas.openai import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    Usage,
)
from app.schemas.sentinel import UserContext, Verdict
from app.services.file_extract import (
    enrich_with_vision,
    extract_many,
    merge_into_prompt,
)

router = APIRouter()


def _flatten_messages(messages: list[ChatMessage]) -> str:
    """Concatenate a chat history into a single 'prompt' string for scanning.

    For MVP simplicity we focus our scanners on the latest user turn; system /
    assistant turns are concatenated for context but not weighted heavily.
    """
    parts = []
    for m in messages:
        role = m.role
        content = m.content or ""
        parts.append(f"[{role}] {content}")
    return "\n".join(parts)


def _last_user_text(messages: list[ChatMessage]) -> str:
    for m in reversed(messages):
        if m.role == "user" and m.content:
            return m.content
    return _flatten_messages(messages)


@router.post("/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(
    body: ChatCompletionRequest,
    request: Request,
    _: str = Depends(require_api_key),
    user: UserContext = Depends(get_user_context),
    x_sensitivity: str | None = Header(default=None),
):
    if body.stream:
        raise HTTPException(status_code=400, detail="Streaming not supported in MVP")

    original_prompt = _last_user_text(body.messages)
    sensitivity = (x_sensitivity or "normal").lower()

    # Extract attachments (text, code, PDF, DOCX, images) and merge their text
    # into the prompt so every existing scanner runs over the file contents
    # exactly like a regular prompt — catching prompt injection / PII / secrets
    # hidden inside an upload.
    attachment_summaries: list[dict] = []
    prompt = original_prompt
    if body.attachments:
        items = [a.model_dump() for a in body.attachments]
        extracted, err = extract_many(items)
        if err:
            attachment_summaries = [a.to_summary() for a in extracted]
            raise HTTPException(
                status_code=413,
                detail={"error": err, "attachments": attachment_summaries},
            )
        # Run multimodal vision description on image attachments (if enabled
        # and credentials are configured) so the resulting text flows through
        # every scanner exactly like OCR / file content.
        await enrich_with_vision(extracted)
        attachment_summaries = [a.to_summary() for a in extracted]
        prompt = merge_into_prompt(original_prompt, extracted)

    state = await run_pipeline(
        user=user,
        prompt=prompt,
        requested_model=body.model,
        sensitivity=sensitivity,
    )
    state.original_prompt = original_prompt
    state.attachments = attachment_summaries

    sentinel_payload = {
        "request_id": state.request_id,
        "verdict": state.verdict.value,
        "output_verdict": state.output_verdict.value,
        "risk": state.risk,
        "output_risk": state.output_risk,
        "model_requested": state.requested_model,
        "model_used": state.selected_model,
        "fallback_used": state.fallback_used,
        "sensitivity": state.sensitivity,
        "block_reason": state.block_reason,
        "redacted_prompt": state.redacted_prompt,
        "findings": [f.model_dump() for f in state.findings],
        "output_findings": [f.model_dump() for f in state.output_findings],
        "risk_breakdown": state.risk_breakdown,
        "opa_reasons": state.opa_reasons,
        "latency_ms": state.latency_ms,
        "attachments": attachment_summaries,
        "explanation": state.explanation,
        "confidence": state.confidence,
        "intent": state.intent,
        "agentic_trace_version": state.agentic_trace_version,
        "agent_steps": state.agent_steps,
        "agent_findings": state.agent_findings,
        "self_corrections": state.self_corrections,
        "reflections": state.reflections,
    }

    if state.verdict == Verdict.BLOCK:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Request blocked by SentinelGuard",
                "sentinel": sentinel_payload,
            },
        )

    return ChatCompletionResponse(
        model=state.selected_model or body.model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=state.final_response or ""),
                finish_reason="stop",
            )
        ],
        usage=Usage(
            prompt_tokens=len(prompt.split()),
            completion_tokens=len((state.final_response or "").split()),
            total_tokens=len(prompt.split()) + len((state.final_response or "").split()),
        ),
        sentinel=sentinel_payload,
    )

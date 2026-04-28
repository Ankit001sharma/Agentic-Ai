"""ReportingAgent — persists request, findings, and emits real-time events."""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import httpx
import redis.asyncio as redis_async

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import AgentTrace, AuditEvent, FindingRow, Request
from app.db.session import SessionLocal
from app.scanners.embedding_jailbreak import embed
from app.schemas.sentinel import ScanState

log = get_logger("agent.reporting")

_STREAM = "sentinelguard:events"


async def _publish(payload: dict[str, Any]) -> None:
    s = get_settings()
    try:
        client = redis_async.from_url(s.redis_url)
        await client.xadd(_STREAM, {"data": json.dumps(payload, default=str)}, maxlen=5000, approximate=True)
        await client.aclose()
    except Exception as e:  # noqa: BLE001
        log.warning("redis_publish_failed", error=str(e))


async def _siem_webhook(payload: dict[str, Any]) -> None:
    s = get_settings()
    if not s.siem_webhook_url:
        return
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            siem = {
                "severity": (
                    "high"
                    if payload.get("verdict") == "BLOCK"
                    else "medium"
                    if payload.get("verdict") in ("ESCALATE", "MASK")
                    else "low"
                ),
                "source": "sentinelguard",
                "event": payload,
            }
            await c.post(s.siem_webhook_url, json=siem)
    except Exception as e:  # noqa: BLE001
        log.warning("siem_webhook_failed", error=str(e))


async def run(state: ScanState) -> ScanState:
    state.finished_at = dt.datetime.now(dt.UTC).timestamp()
    state.latency_ms = int((state.finished_at - state.started_at) * 1000) if state.started_at else 0

    # Compute embedding for vector recall (best effort)
    vec = embed(state.prompt) if state.prompt else None

    # Persist
    try:
        async with SessionLocal() as db:
            row = Request(
                id=state.request_id,
                user_id=state.user.user_id,
                session_id=state.user.session_id,
                requested_model=state.requested_model,
                selected_model=state.selected_model,
                fallback_used=state.fallback_used,
                sensitivity=state.sensitivity,
                prompt=state.prompt,
                redacted_prompt=state.redacted_prompt,
                response=state.llm_response,
                final_response=state.final_response,
                risk=state.risk,
                output_risk=state.output_risk,
                verdict=state.verdict.value,
                output_verdict=state.output_verdict.value,
                block_reason=state.block_reason,
                risk_breakdown=state.risk_breakdown,
                latency_ms=state.latency_ms,
                embedding=vec,
            )
            db.add(row)
            for f in state.findings:
                db.add(
                    FindingRow(
                        request_id=row.id,
                        side="input",
                        category=f.category,
                        scanner=f.scanner,
                        severity=f.severity,
                        evidence=f.evidence,
                        extra=f.metadata,
                    )
                )
            for f in state.output_findings:
                db.add(
                    FindingRow(
                        request_id=row.id,
                        side="output",
                        category=f.category,
                        scanner=f.scanner,
                        severity=f.severity,
                        evidence=f.evidence,
                        extra=f.metadata,
                    )
                )
            db.add(
                AuditEvent(
                    request_id=row.id,
                    event_type="request.completed",
                    payload={
                        "events": state.audit_events,
                        "verdict": state.verdict.value,
                        "output_verdict": state.output_verdict.value,
                        "risk": state.risk,
                        "output_risk": state.output_risk,
                    },
                )
            )
            db.add(
                AgentTrace(
                    request_id=row.id,
                    agent_steps=list(state.agent_steps or []),
                    assistant_steps=list(state.assistant_steps or []),
                    explanation=dict(state.explanation or {}),
                    agent_findings=list(state.agent_findings or []),
                    agentic_trace_version=state.agentic_trace_version or "2",
                )
            )
            await db.commit()
    except Exception as e:  # noqa: BLE001
        log.warning("audit_persist_failed", error=str(e))

    # Real-time event payload (compact)
    payload = {
        "type": "request",
        "request_id": state.request_id,
        "user": state.user.user_id,
        "tier": state.user.tier,
        "model_requested": state.requested_model,
        "model_used": state.selected_model,
        "fallback": state.fallback_used,
        "verdict": state.verdict.value,
        "output_verdict": state.output_verdict.value,
        "risk": state.risk,
        "output_risk": state.output_risk,
        "latency_ms": state.latency_ms,
        "categories_in": sorted({f.category for f in state.findings}),
        "categories_out": sorted({f.category for f in state.output_findings}),
        "prompt_preview": state.prompt[:160],
        "response_preview": (state.final_response or "")[:160],
        "before_after": {
            "prompt_before": state.prompt,
            "prompt_after": state.redacted_prompt or state.prompt,
            "response_before": state.llm_response,
            "response_after": state.final_response,
        },
        "ts": state.finished_at,
        "sentinel": {
            "explanation": state.explanation,
            "agent_steps": state.agent_steps,
            "agent_findings": state.agent_findings,
            "confidence": state.confidence,
            "agentic_trace_version": state.agentic_trace_version,
        },
    }
    await _publish(payload)
    await _siem_webhook(payload)

    state.audit_events.append({"agent": "reporting", "persisted": True})
    return state

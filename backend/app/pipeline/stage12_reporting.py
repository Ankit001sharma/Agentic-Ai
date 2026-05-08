"""Stage 12 — Reporting & Audit.

Writes a fully-redacted audit record to:
  1. Postgres  (audit_log table)
  2. Redis Streams  (sentinelguard:events — same stream as /api/events SSE)
  3. SIEM webhook  (optional, fire-and-forget)
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.pipeline.base import Stage
from app.schemas.sentinel import ScanState

log = get_logger("pipeline.stage12")

_STREAM_KEY = "sentinelguard:events"
_STREAM_MAXLEN = 10_000


class ReportingStage(Stage):
    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client

    async def run(self, state: ScanState) -> ScanState:
        state.pipeline_stage = 12
        s = get_settings()

        state.finished_at = time.time()
        state.latency_ms = int((state.finished_at - state.started_at) * 1000)

        record = _build_audit_record(state)
        live_payload = _build_live_event_payload(state)

        # Fire all reporting tasks concurrently
        tasks: list[asyncio.Task] = [
            asyncio.create_task(self._write_redis_stream(live_payload)),
        ]
        if s.siem_webhook_url:
            merged = {**record, **live_payload}
            tasks.append(asyncio.create_task(self._siem_webhook(merged, s.siem_webhook_url)))

        # DB write — attempt but don't fail the pipeline on DB error
        tasks.append(asyncio.create_task(self._write_db(state, record)))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, BaseException):
                log.warning("stage12_report_error", error=str(r))

        try:
            await self._persist_request_orm(state)
        except Exception as exc:  # noqa: BLE001
            log.warning("stage12_orm_error", error=str(exc))

        log.info(
            "stage12_done",
            request_id=state.request_id,
            latency_ms=state.latency_ms,
            verdict=state.verdict.value,
        )
        return state

    async def _write_redis_stream(self, record: dict[str, Any]) -> None:
        await self._redis.xadd(
            _STREAM_KEY,
            {"data": json.dumps(record)},
            maxlen=_STREAM_MAXLEN,
            approximate=True,
        )

    async def _siem_webhook(self, record: dict[str, Any], url: str) -> None:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json=record)

    async def _write_db(self, state: ScanState, record: dict[str, Any]) -> None:
        try:
            from app.db.session import SessionLocal
            from sqlalchemy import text

            async with SessionLocal() as session:
                await session.execute(
                    text(
                        """
                        INSERT INTO audit_log (
                            request_id, user_id, conv_id, verdict, risk,
                            tool_id, tool_executed, simulated, latency_ms,
                            findings_json, tool_args_json, tool_result_json,
                            pipeline_error_json, output_verdict, created_at
                        ) VALUES (
                            :request_id, :user_id, :conv_id, :verdict, :risk,
                            :tool_id, :tool_executed, :simulated, :latency_ms,
                            :findings_json, :tool_args_json, :tool_result_json,
                            :pipeline_error_json, :output_verdict, now()
                        )
                        """
                    ),
                    {
                        "request_id": state.request_id,
                        "user_id": state.user.user_id,
                        "conv_id": state.conv_id,
                        "verdict": state.verdict.value,
                        "risk": state.risk,
                        "tool_id": state.tool_id,
                        "tool_executed": state.tool_executed,
                        "simulated": state.simulate,
                        "latency_ms": state.latency_ms,
                        "findings_json": json.dumps([f.model_dump() for f in state.findings]),
                        "tool_args_json": json.dumps(_redact_args(state.tool_args)),
                        # tool_result is already redacted by Stage 11b before we reach here
                        "tool_result_json": json.dumps(state.tool_result or {}),
                        "pipeline_error_json": json.dumps(state.pipeline_error or {}),
                        "output_verdict": state.output_verdict.value,
                    },
                )
                await session.commit()
        except Exception as exc:  # noqa: BLE001
            log.warning("stage12_db_error", error=str(exc))

    async def _persist_request_orm(self, state: ScanState) -> None:
        from sqlalchemy import select

        from app.db.models import AgentTrace, AuditEvent, FindingRow, Request
        from app.db.session import SessionLocal
        from app.scanners.embedding_jailbreak import embed

        vec = embed(state.prompt) if state.prompt else None

        async with SessionLocal() as db:
            res = await db.execute(select(Request).where(Request.id == state.request_id))
            if res.scalar_one_or_none() is not None:
                return

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
                verdict=state.verdict.value if hasattr(state.verdict, "value") else str(state.verdict),
                output_verdict=(
                    state.output_verdict.value
                    if hasattr(state.output_verdict, "value")
                    else str(state.output_verdict)
                ),
                block_reason=state.block_reason,
                risk_breakdown=state.risk_breakdown or {},
                latency_ms=state.latency_ms,
                embedding=vec,
            )
            db.add(row)
            await db.flush()
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
                    event_type="pipeline.completed",
                    payload={
                        "conv_id": state.conv_id,
                        "intent": state.intent,
                        "tool_id": state.tool_id,
                        "tool_executed": state.tool_executed,
                        "pipeline_stage": state.pipeline_stage,
                        "verdict": state.verdict.value,
                    },
                )
            )
            trace_steps: list[dict[str, Any]] = list(state.agent_steps or [])
            if not trace_steps and state.stages_executed:
                # Use the runner-tracked execution sequence so the persisted
                # trace reflects reality (Response → Reporting → Adaptive).
                trace_steps = [
                    {"stage": label, "name": f"stage{label}"}
                    for label in state.stages_executed
                ]
            elif not trace_steps and state.pipeline_stage:
                trace_steps = [
                    {"stage": i + 1, "name": f"stage{i+1:02d}"} for i in range(state.pipeline_stage)
                ]
            db.add(
                AgentTrace(
                    request_id=row.id,
                    agent_steps=trace_steps,
                    assistant_steps=list(state.assistant_steps or []),
                    explanation=dict(state.explanation or {}),
                    agent_findings=list(state.agent_findings or []),
                    agentic_trace_version=state.agentic_trace_version or "2",
                )
            )
            await db.commit()


def _build_live_event_payload(state: ScanState) -> dict[str, Any]:
    """SSE payload consumed by the dashboard Live Stream (matches legacy reporting)."""
    intent_detail = None
    if state.intent_result is not None:
        ir = state.intent_result
        intent_detail = {
            "intent": ir.intent,
            "tool_id": ir.tool_id,
            "confidence": ir.confidence,
            "ambiguous": ir.ambiguous,
            "clarification_needed": ir.clarification_needed,
            "entities": ir.entities.model_dump(),
        }
    fn_detail = None
    if state.fn_call_result is not None:
        fc = state.fn_call_result
        fn_detail = {
            "tool_id": fc.tool_id,
            "rationale": fc.rationale,
            "missing_required_fields": fc.missing_required_fields,
        }
    return {
        "type": "request",
        "request_id": state.request_id,
        "user": state.user.user_id,
        "tier": state.user.tier,
        "conv_id": state.conv_id,
        "model_requested": state.requested_model,
        "model_used": state.selected_model,
        "fallback": state.fallback_used,
        "verdict": state.verdict.value,
        "output_verdict": state.output_verdict.value,
        "risk": state.risk,
        "output_risk": state.output_risk,
        "latency_ms": state.latency_ms,
        "pipeline_stage": state.pipeline_stage,
        "intent": state.intent,
        "tool_id": state.tool_id,
        "tool_executed": state.tool_executed,
        "simulated": state.simulate,
        "intent_detail": intent_detail,
        "fn_call_detail": fn_detail,
        "categories_in": sorted({f.category for f in state.findings}),
        "categories_out": sorted({f.category for f in state.output_findings}),
        "prompt_preview": (state.prompt or "")[:160],
        "response_preview": (state.final_response or "")[:160],
        "pipeline_error": state.pipeline_error,
        "ts": state.finished_at,
        "sentinel": {
            "explanation": state.explanation,
            "agent_steps": state.agent_steps,
            "agent_findings": state.agent_findings,
            "confidence": state.confidence,
            "agentic_trace_version": state.agentic_trace_version,
        },
    }


def _build_audit_record(state: ScanState) -> dict[str, Any]:
    return {
        "request_id": state.request_id,
        "user_id": state.user.user_id,
        "conv_id": state.conv_id,
        "verdict": state.verdict.value,
        "risk": state.risk,
        "tool_id": state.tool_id,
        "tool_executed": state.tool_executed,
        "simulated": state.simulate,
        "latency_ms": state.latency_ms,
        "findings_count": len(state.findings),
        "output_verdict": state.output_verdict.value,
        "output_risk": state.output_risk,
        "output_findings_count": len(state.output_findings),
        "pipeline_error": state.pipeline_error,
        "ts": state.finished_at,
    }


def _redact_args(args: dict[str, Any]) -> dict[str, Any]:
    """Remove email bodies and long strings from audit record."""
    redacted: dict[str, Any] = {}
    for k, v in args.items():
        if isinstance(v, str) and len(v) > 200:
            redacted[k] = v[:200] + "[…redacted]"
        else:
            redacted[k] = v
    return redacted

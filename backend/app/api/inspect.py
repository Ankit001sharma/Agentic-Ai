"""GET /api/inspect/{request_id} — full request detail for the dashboard inspector."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.api.deps import require_api_key
from app.db.models import AgentTrace, FindingRow, Request
from app.db.session import SessionLocal

router = APIRouter()


@router.get("/{request_id}")
async def inspect_request(request_id: str, _: str = Depends(require_api_key)) -> dict[str, Any]:
    async with SessionLocal() as db:
        res = await db.execute(
            select(Request)
            .options(selectinload(Request.findings))
            .where(Request.id == request_id)
        )
        row = res.scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="request not found")

        tres = await db.execute(select(AgentTrace).where(AgentTrace.request_id == request_id))
        trace = tres.scalar_one_or_none()

        audit_row = (
            await db.execute(
                text(
                    """
                    SELECT id, request_id, user_id, conv_id, verdict, risk, tool_id,
                           tool_executed, simulated, latency_ms, findings_json, tool_args_json,
                           tool_result_json, pipeline_error_json, output_verdict, created_at
                    FROM audit_log
                    WHERE request_id = :rid
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"rid": request_id},
            )
        ).mappings().first()

        findings_in = [f for f in row.findings if f.side == "input"]
        findings_out = [f for f in row.findings if f.side == "output"]

        audit_blob: dict[str, Any] = {}
        if audit_row:
            audit_blob = {
                "audit_log_id": audit_row["id"],
                "conv_id": audit_row["conv_id"],
                "tool_id": audit_row["tool_id"],
                "tool_executed": audit_row["tool_executed"],
                "simulated": audit_row["simulated"],
                "output_verdict": audit_row["output_verdict"],
                "findings_json": _maybe_json(audit_row["findings_json"]),
                "tool_args": _maybe_json(audit_row["tool_args_json"]),
                "tool_result": _maybe_json(audit_row["tool_result_json"]),
                "pipeline_error": _maybe_json(audit_row["pipeline_error_json"]),
            }

        return {
            "request_id": row.id,
            "user_id": row.user_id,
            "session_id": row.session_id,
            "conv_id": audit_blob.get("conv_id"),
            "requested_model": row.requested_model,
            "selected_model": row.selected_model,
            "fallback_used": row.fallback_used,
            "sensitivity": row.sensitivity,
            "prompt": row.prompt,
            "redacted_prompt": row.redacted_prompt,
            "llm_response": row.response,
            "final_response": row.final_response,
            "verdict": row.verdict,
            "output_verdict": row.output_verdict,
            "risk": row.risk,
            "output_risk": row.output_risk,
            "block_reason": row.block_reason,
            "risk_breakdown": row.risk_breakdown,
            "latency_ms": row.latency_ms,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "findings_input": [_finding_dict(f) for f in findings_in],
            "findings_output": [_finding_dict(f) for f in findings_out],
            "agent_trace": {
                "agent_steps": trace.agent_steps if trace else [],
                "assistant_steps": trace.assistant_steps if trace else [],
                "explanation": trace.explanation if trace else None,
                "agent_findings": trace.agent_findings if trace else [],
                "agentic_trace_version": trace.agentic_trace_version if trace else None,
            }
            if trace
            else None,
            "audit": audit_blob if audit_row else None,
        }


def _maybe_json(raw: str | None) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return raw


def _finding_dict(f: FindingRow) -> dict[str, Any]:
    return {
        "category": f.category,
        "scanner": f.scanner,
        "severity": f.severity,
        "evidence": f.evidence,
        "extra": f.extra or {},
        "side": f.side,
    }

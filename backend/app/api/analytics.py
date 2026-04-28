"""Read-only analytics endpoints powering the dashboard."""

from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, select

from app.api.deps import require_api_key
from app.db.models import FindingRow, Request, RiskGraphNode
from app.db.session import SessionLocal

router = APIRouter()


@router.get("/summary")
async def summary(_: str = Depends(require_api_key)):
    async with SessionLocal() as db:
        total = (await db.execute(select(func.count(Request.id)))).scalar() or 0
        blocked = (
            await db.execute(select(func.count(Request.id)).where(Request.verdict == "BLOCK"))
        ).scalar() or 0
        masked = (
            await db.execute(select(func.count(Request.id)).where(Request.verdict == "MASK"))
        ).scalar() or 0
        escalated = (
            await db.execute(select(func.count(Request.id)).where(Request.verdict == "ESCALATE"))
        ).scalar() or 0
        avg_risk = (await db.execute(select(func.avg(Request.risk)))).scalar() or 0
        avg_latency = (await db.execute(select(func.avg(Request.latency_ms)))).scalar() or 0
        return {
            "total": int(total),
            "blocked": int(blocked),
            "masked": int(masked),
            "escalated": int(escalated),
            "block_rate": round((blocked / total * 100) if total else 0, 2),
            "avg_risk": round(float(avg_risk), 2),
            "avg_latency_ms": round(float(avg_latency), 2),
        }


@router.get("/threats_by_hour")
async def threats_by_hour(_: str = Depends(require_api_key)):
    """Last 24 hours, bucketed."""
    since = dt.datetime.now(dt.UTC) - dt.timedelta(hours=24)
    async with SessionLocal() as db:
        bucket = func.date_trunc("hour", Request.created_at).label("hour")
        res = await db.execute(
            select(bucket, Request.verdict, func.count(Request.id))
            .where(Request.created_at >= since)
            .group_by(bucket, Request.verdict)
            .order_by(bucket)
        )
        out: dict[str, dict[str, int]] = {}
        for hour, verdict, cnt in res.all():
            key = hour.isoformat() if hour else "unknown"
            out.setdefault(key, {"ALLOW": 0, "MASK": 0, "ESCALATE": 0, "BLOCK": 0})
            out[key][verdict] = int(cnt)
        return [{"hour": k, **v} for k, v in out.items()]


@router.get("/top_threats")
async def top_threats(_: str = Depends(require_api_key)):
    async with SessionLocal() as db:
        res = await db.execute(
            select(FindingRow.category, func.count(FindingRow.id).label("count"))
            .group_by(FindingRow.category)
            .order_by(desc("count"))
            .limit(10)
        )
        return [{"category": c, "count": int(n)} for c, n in res.all()]


@router.get("/model_usage")
async def model_usage(_: str = Depends(require_api_key)):
    async with SessionLocal() as db:
        res = await db.execute(
            select(Request.selected_model, func.count(Request.id))
            .where(Request.selected_model.isnot(None))
            .group_by(Request.selected_model)
        )
        return [{"model": m or "unknown", "count": int(c)} for m, c in res.all()]


@router.get("/top_risky_users")
async def top_risky_users(_: str = Depends(require_api_key)):
    async with SessionLocal() as db:
        res = await db.execute(
            select(RiskGraphNode.key, RiskGraphNode.score, RiskGraphNode.attrs)
            .where(RiskGraphNode.node_type == "user")
            .order_by(RiskGraphNode.score.desc())
            .limit(10)
        )
        return [{"user_id": k, "score": float(s), "attrs": a or {}} for k, s, a in res.all()]


@router.get("/recent")
async def recent_requests(limit: int = 20, _: str = Depends(require_api_key)):
    async with SessionLocal() as db:
        res = await db.execute(
            select(Request).order_by(Request.created_at.desc()).limit(min(limit, 100))
        )
        rows = res.scalars().all()
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "verdict": r.verdict,
                "output_verdict": r.output_verdict,
                "risk": r.risk,
                "output_risk": r.output_risk,
                "model_used": r.selected_model,
                "fallback": r.fallback_used,
                "latency_ms": r.latency_ms,
                "prompt_preview": (r.prompt or "")[:160],
                "response_preview": (r.final_response or "")[:160],
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

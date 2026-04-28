"""Human-in-Loop review queue endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
import redis.asyncio as redis_async

from app.api.deps import require_api_key
from app.core.config import get_settings
from app.db.models import ReviewQueueItem
from app.db.session import SessionLocal

router = APIRouter()


class DecisionPayload(BaseModel):
    decision: str  # APPROVE | DENY
    reason: str | None = None
    analyst: str | None = None


@router.get("/pending")
async def list_pending(_: str = Depends(require_api_key)):
    async with SessionLocal() as db:
        res = await db.execute(
            select(ReviewQueueItem)
            .where(ReviewQueueItem.status == "PENDING")
            .order_by(ReviewQueueItem.created_at.desc())
            .limit(50)
        )
        items = res.scalars().all()
        return [
            {
                "id": i.id,
                "request_id": i.request_id,
                "user_id": i.user_id,
                "prompt": i.prompt,
                "risk": i.risk,
                "findings": i.findings,
                "status": i.status,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in items
        ]


@router.post("/{request_id}/decision")
async def decide(request_id: str, payload: DecisionPayload, _: str = Depends(require_api_key)):
    decision = payload.decision.upper()
    if decision not in ("APPROVE", "DENY"):
        raise HTTPException(status_code=400, detail="decision must be APPROVE or DENY")

    s = get_settings()
    try:
        client = redis_async.from_url(s.redis_url)
        await client.set(f"sentinelguard:review:decision:{request_id}", decision, ex=300)
        await client.aclose()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"redis_unavailable: {e}") from e

    async with SessionLocal() as db:
        res = await db.execute(
            select(ReviewQueueItem).where(ReviewQueueItem.request_id == request_id)
        )
        item = res.scalar_one_or_none()
        if item is not None:
            item.decision_by = payload.analyst or "unknown"
            item.decision_reason = payload.reason
            await db.commit()

    return {"ok": True, "request_id": request_id, "decision": decision}

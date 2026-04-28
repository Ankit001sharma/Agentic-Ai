"""Active + AI-suggested policies API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.api.deps import require_api_key
from app.db.models import Policy
from app.db.session import SessionLocal

router = APIRouter()


@router.get("")
async def list_policies(_: str = Depends(require_api_key)):
    async with SessionLocal() as db:
        res = await db.execute(select(Policy).order_by(Policy.created_at.desc()))
        items = res.scalars().all()
        return [
            {
                "id": p.id,
                "name": p.name,
                "rego": p.rego,
                "enabled": p.enabled,
                "suggested": p.suggested,
                "suggested_by": p.suggested_by,
                "suggested_reason": p.suggested_reason,
                "approved": p.approved,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in items
        ]


@router.post("/{policy_id}/approve")
async def approve(policy_id: int, _: str = Depends(require_api_key)):
    async with SessionLocal() as db:
        res = await db.execute(select(Policy).where(Policy.id == policy_id))
        p = res.scalar_one_or_none()
        if p is None:
            raise HTTPException(status_code=404, detail="policy not found")
        p.approved = True
        p.enabled = True
        await db.commit()
        return {"ok": True}


@router.post("/{policy_id}/reject")
async def reject(policy_id: int, _: str = Depends(require_api_key)):
    async with SessionLocal() as db:
        res = await db.execute(select(Policy).where(Policy.id == policy_id))
        p = res.scalar_one_or_none()
        if p is None:
            raise HTTPException(status_code=404, detail="policy not found")
        p.approved = False
        p.enabled = False
        await db.commit()
        return {"ok": True}

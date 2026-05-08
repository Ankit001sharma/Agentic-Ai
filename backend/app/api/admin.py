"""Stub admin endpoints — organization, members (replace with DB-backed impl)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import require_api_key

router = APIRouter()


@router.get("/organization")
async def get_org(_: str = Depends(require_api_key)) -> dict[str, Any]:
    return {
        "id": "org-demo",
        "name": "SentinelGuard Demo",
        "tier": "enterprise",
        "region": "global",
        "default_sensitivity": "normal",
    }


class OrgUpdate(BaseModel):
    name: str | None = None
    region: str | None = None


@router.patch("/organization")
async def patch_org(_body: OrgUpdate, _: str = Depends(require_api_key)) -> dict[str, str]:
    return {"status": "ok", "note": "stub — not persisted"}


@router.get("/members")
async def list_members(_: str = Depends(require_api_key)) -> list[dict[str, Any]]:
    return [
        {
            "id": "u-admin",
            "email": "admin@sentinel.local",
            "role": "admin",
            "status": "active",
        },
        {
            "id": "u-analyst",
            "email": "analyst@sentinel.local",
            "role": "analyst",
            "status": "active",
        },
    ]


class InviteBody(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    role: str = Field(..., pattern="^(admin|analyst|viewer)$")


@router.post("/members/invite")
async def invite_member(_body: InviteBody, _: str = Depends(require_api_key)) -> dict[str, str]:
    return {"status": "invited", "note": "stub — email not sent"}

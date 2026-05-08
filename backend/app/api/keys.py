"""Stub API key management — in-memory until a keys table exists."""

from __future__ import annotations

import secrets
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_api_key

router = APIRouter()

_store: dict[str, dict[str, Any]] = {}


class KeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    scopes: list[str] = Field(default_factory=lambda: ["read", "write"])


@router.get("")
async def list_keys(_: str = Depends(require_api_key)) -> list[dict[str, Any]]:
    return [
        {
            "id": k,
            "name": v["name"],
            "scopes": v["scopes"],
            "prefix": v["prefix"],
            "created_at": v["created_at"],
            "last_used_at": v.get("last_used_at"),
        }
        for k, v in _store.items()
    ]


@router.post("")
async def create_key(body: KeyCreate, _: str = Depends(require_api_key)) -> dict[str, Any]:
    kid = secrets.token_hex(8)
    raw = f"sg_{secrets.token_urlsafe(24)}"
    _store[kid] = {
        "name": body.name,
        "scopes": body.scopes,
        "prefix": raw[:12],
        "secret": raw,
        "created_at": time.time(),
        "last_used_at": None,
    }
    return {"id": kid, "key": raw, "prefix": raw[:12], "warning": "Copy now; secret is not shown again."}


@router.delete("/{key_id}")
async def revoke_key(key_id: str, _: str = Depends(require_api_key)) -> dict[str, str]:
    if key_id not in _store:
        raise HTTPException(status_code=404, detail="key not found")
    del _store[key_id]
    return {"status": "revoked"}

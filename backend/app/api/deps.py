"""FastAPI shared dependencies (auth, identity)."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.core.config import get_settings
from app.schemas.sentinel import UserContext


async def require_api_key(x_sentinel_key: str | None = Header(default=None)) -> str:
    settings = get_settings()
    if not x_sentinel_key or x_sentinel_key != settings.sentinel_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-Sentinel-Key",
        )
    return x_sentinel_key


async def get_user_context(
    x_user_id: str | None = Header(default=None),
    x_user_tier: str | None = Header(default=None),
    x_session_id: str | None = Header(default=None),
    x_user_region: str | None = Header(default=None),
    x_sensitivity: str | None = Header(default=None),
    x_auth_type: str | None = Header(default=None),
    x_user_role: str | None = Header(default=None),
    x_resource: str | None = Header(default=None),
) -> UserContext:
    return UserContext(
        user_id=x_user_id or "anonymous",
        tier=(x_user_tier or "free").lower(),
        region=(x_user_region or "global").lower(),
        session_id=x_session_id or "default",
        auth_type=(x_auth_type or "human").lower(),
        role=(x_user_role or "viewer").lower(),
        resource=(x_resource.lower() if x_resource else None),
    )

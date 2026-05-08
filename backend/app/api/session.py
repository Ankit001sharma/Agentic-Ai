"""DELETE /api/v2/session/{conv_id} — end a conversation session.

Promotes STM context to long-term Postgres memory, then removes the Redis key.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_user_context, require_api_key
from app.core.logging import get_logger
from app.memory.stm import ShortTermMemory
from app.schemas.sentinel import UserContext

log = get_logger("api.session")

router = APIRouter()


@router.get("/sessions", status_code=200)
async def list_sessions(
    request: Request,
    _: str = Depends(require_api_key),
    user: UserContext = Depends(get_user_context),
) -> list[dict[str, Any]]:
    """List active STM conversation keys for the current user (Redis SCAN)."""
    redis = request.app.state.redis
    prefix = f"stm:{user.user_id}:"
    out: list[dict[str, Any]] = []
    async for key in redis.scan_iter(match=f"{prefix}*", count=50):
        if isinstance(key, bytes):
            key = key.decode()
        conv_id = key.split(":", 2)[-1]
        raw = await redis.get(key)
        ctx: dict[str, Any] = {}
        if raw:
            try:
                ctx = json.loads(raw) if isinstance(raw, str) else json.loads(raw.decode())
            except Exception:  # noqa: BLE001
                ctx = {}
        ttl = await redis.ttl(key)
        out.append({"conv_id": conv_id, "ttl_seconds": ttl, "context_preview": ctx})
    out.sort(key=lambda x: x["conv_id"])
    return out


@router.delete("/session/{conv_id}", status_code=200)
async def end_session(
    conv_id: str,
    request: Request,
    _: str = Depends(require_api_key),
    user: UserContext = Depends(get_user_context),
) -> dict:
    """Promote STM → long-term memory and clear the Redis key."""
    stm = ShortTermMemory(request.app.state.redis)
    await stm.promote_to_long_term(user.user_id, conv_id)
    log.info("session_ended", user_id=user.user_id, conv_id=conv_id)
    return {"status": "ok", "conv_id": conv_id}

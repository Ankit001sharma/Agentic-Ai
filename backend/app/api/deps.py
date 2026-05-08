"""FastAPI shared dependencies (auth, identity)."""

from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.sentinel import UserContext

log = get_logger("api.deps")


async def require_api_key(x_sentinel_key: str | None = Header(default=None)) -> str:
    settings = get_settings()
    if not x_sentinel_key or x_sentinel_key != settings.sentinel_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-Sentinel-Key",
        )
    return x_sentinel_key


async def _load_historical_risk(user_id: str) -> float:
    """Read the user's persisted risk score from the user_risk table.

    Stage 13 (AdaptiveRiskStage) writes this row on every non-anonymous
    request; without loading it back here, every request started from 0.0
    and stage 13 effectively overwrote the DB with the same delta —
    breaking the cross-request adaptive loop.
    """
    if user_id == "anonymous":
        return 0.0
    try:
        from sqlalchemy import text

        from app.db.session import SessionLocal

        async with SessionLocal() as session:
            result = await session.execute(
                text("SELECT risk_score FROM user_risk WHERE user_id = :uid"),
                {"uid": user_id},
            )
            row = result.first()
            return float(row[0]) if row and row[0] is not None else 0.0
    except Exception as exc:  # noqa: BLE001
        # Fail-soft: missing/unreachable DB must not block the request.
        log.warning("historical_risk_load_failed", user_id=user_id, error=str(exc))
        return 0.0


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
    user_id = x_user_id or "anonymous"
    historical_risk = await _load_historical_risk(user_id)
    return UserContext(
        user_id=user_id,
        tier=(x_user_tier or "free").lower(),
        region=(x_user_region or "global").lower(),
        session_id=x_session_id or "default",
        auth_type=(x_auth_type or "human").lower(),
        role=(x_user_role or "viewer").lower(),
        resource=(x_resource.lower() if x_resource else None),
        historical_risk=historical_risk,
    )

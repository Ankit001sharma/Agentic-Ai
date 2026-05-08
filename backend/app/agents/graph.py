"""Pipeline orchestrator — thin shim over the 14-stage sequential pipeline.

All execution routes through app.pipeline.runner.  The agentic/LangGraph path
has been removed; this module is kept for import compatibility only.
"""

from __future__ import annotations

from app.pipeline.runner import run_pipeline as run_pipeline  # re-export
from app.schemas.sentinel import ScanState, UserContext


async def run_legacy_pipeline(
    *,
    user: UserContext,
    prompt: str,
    requested_model: str,
    sensitivity: str = "normal",
) -> ScanState:
    """Compatibility wrapper — delegates to the 14-stage pipeline runner."""
    import uuid, datetime as dt, redis.asyncio as aioredis
    from app.core.config import get_settings
    s = get_settings()
    redis_client = aioredis.from_url(s.redis_url, decode_responses=True)
    try:
        return await run_pipeline(
            prompt=prompt,
            user=user,
            conv_id=uuid.uuid4().hex[:16],
            redis_client=redis_client,
            simulate=False,
            requested_model=requested_model,
            sensitivity=sensitivity,
        )
    finally:
        await redis_client.aclose()

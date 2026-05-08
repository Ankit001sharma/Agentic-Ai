"""Rich health checks for the dashboard."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import redis.asyncio as redis_async
from fastapi import APIRouter, Depends

from app.api.deps import require_api_key
from app.core.config import get_settings
from sqlalchemy import text

from app.db.session import SessionLocal

router = APIRouter()


@router.get("")
async def gateway_health(_: str = Depends(require_api_key)) -> dict[str, Any]:
    """Aggregate dependency status (vLLM probe is optional / may be slow)."""
    s = get_settings()
    checks: dict[str, Any] = {}

    async def _pg() -> str:
        try:
            async with SessionLocal() as db:
                await db.execute(text("SELECT 1"))
            return "ok"
        except Exception as e:  # noqa: BLE001
            return f"error: {e}"

    async def _redis() -> str:
        try:
            client = redis_async.from_url(s.redis_url)
            await client.ping()
            await client.aclose()
            return "ok"
        except Exception as e:  # noqa: BLE001
            return f"error: {e}"

    async def _opa() -> str:
        try:
            async with httpx.AsyncClient(timeout=2.0) as c:
                r = await c.get(f"{s.opa_url.rstrip('/')}/health")
                return "ok" if r.status_code < 500 else f"http_{r.status_code}"
        except Exception as e:  # noqa: BLE001
            return f"error: {e}"

    async def _vllm() -> str:
        base = (s.vllm_base_url or "").strip().rstrip("/")
        if not base:
            return "not_configured"
        try:
            async with httpx.AsyncClient(timeout=3.0, follow_redirects=True) as c:
                r = await c.get(f"{base}/v1/models")
                return "ok" if r.status_code < 500 else f"http_{r.status_code}"
        except Exception as e:  # noqa: BLE001
            return f"error: {e}"

    pg, rd, opa, vllm = await asyncio.gather(_pg(), _redis(), _opa(), _vllm())
    checks["postgres"] = {"status": pg}
    checks["redis"] = {"status": rd}
    checks["opa"] = {"status": opa}
    checks["vllm"] = {"status": vllm}
    checks["qdrant"] = {"status": "unknown", "note": "probe not implemented"}
    checks["langfuse"] = {"status": "unknown", "note": "set LANGFUSE_ENABLED to probe"}
    checks["code_sandbox"] = {"status": "unknown", "note": "internal only"}

    statuses = [v.get("status") for v in checks.values() if isinstance(v, dict)]
    bad = [s for s in statuses if s and not str(s).startswith("ok") and s != "not_configured" and s != "unknown"]
    return {"overall": "healthy" if not bad else "degraded", "checks": checks}

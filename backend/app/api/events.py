"""SSE event stream consumed by the frontend Live Feed."""

from __future__ import annotations

import asyncio
import json

import redis.asyncio as redis_async
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("api.events")
router = APIRouter()

_STREAM = "sentinelguard:events"


@router.get("/events")
async def events_stream():
    s = get_settings()

    async def gen():
        # last_id starts at "$" => only new events
        last_id = "$"
        client = None
        try:
            client = redis_async.from_url(s.redis_url)
            while True:
                try:
                    resp = await client.xread({_STREAM: last_id}, count=20, block=15000)
                except Exception as e:  # noqa: BLE001
                    log.warning("xread_error", error=str(e))
                    await asyncio.sleep(1.0)
                    continue
                if not resp:
                    yield {"event": "ping", "data": "{}"}
                    continue
                for _stream, entries in resp:
                    for entry_id, fields in entries:
                        last_id = entry_id
                        data = fields.get(b"data") if isinstance(fields, dict) else None
                        if data is None and isinstance(fields, dict):
                            data = fields.get("data")
                        if isinstance(data, bytes):
                            data = data.decode()
                        try:
                            payload = json.loads(data) if data else {}
                        except Exception:  # noqa: BLE001
                            payload = {"raw": str(data)}
                        yield {
                            "event": payload.get("type", "message"),
                            "id": entry_id.decode() if isinstance(entry_id, bytes) else str(entry_id),
                            "data": json.dumps(payload),
                        }
        finally:
            if client is not None:
                await client.aclose()

    return EventSourceResponse(gen())

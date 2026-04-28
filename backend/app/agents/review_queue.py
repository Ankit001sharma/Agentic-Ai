"""ReviewQueueAgent — Human-in-Loop review with Redis-backed pending queue.

If the verdict is ESCALATE we:
1. Persist a ReviewQueueItem in Postgres
2. Push request_id onto Redis list `sentinelguard:review:pending`
3. Wait for `sentinelguard:review:decision:<request_id>` key to appear (analyst sets it
   via the API), or timeout after `REVIEW_TIMEOUT_SECONDS` and auto-allow.
"""

from __future__ import annotations

import asyncio
import json

import redis.asyncio as redis_async

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import ReviewQueueItem
from app.db.session import SessionLocal
from app.schemas.sentinel import ScanState, Verdict

log = get_logger("agent.review")

_PENDING_LIST = "sentinelguard:review:pending"
_DECISION_KEY = "sentinelguard:review:decision:"  # + request_id
_STREAM = "sentinelguard:events"


async def _publish_event(payload: dict) -> None:
    s = get_settings()
    try:
        client = redis_async.from_url(s.redis_url)
        await client.xadd(_STREAM, {"data": json.dumps(payload)})
        await client.aclose()
    except Exception as e:  # noqa: BLE001
        log.warning("redis_publish_failed", error=str(e))


async def run(state: ScanState) -> ScanState:
    if state.verdict != Verdict.ESCALATE:
        return state

    s = get_settings()
    timeout = s.review_timeout_seconds
    rid = state.request_id

    findings_json = [f.model_dump() for f in state.findings]

    # Persist review item
    try:
        async with SessionLocal() as db:
            item = ReviewQueueItem(
                request_id=rid,
                user_id=state.user.user_id,
                prompt=state.prompt,
                risk=state.risk,
                findings=findings_json,
                status="PENDING",
            )
            db.add(item)
            await db.commit()
    except Exception as e:  # noqa: BLE001
        log.warning("review_persist_failed", error=str(e))

    await _publish_event(
        {
            "type": "review.pending",
            "request_id": rid,
            "user": state.user.user_id,
            "risk": state.risk,
            "prompt": state.prompt[:240],
            "findings": findings_json[:10],
        }
    )

    # Push to Redis queue + poll for decision
    try:
        client = redis_async.from_url(s.redis_url)
        await client.lpush(_PENDING_LIST, rid)
        decision_key = _DECISION_KEY + rid
        deadline = asyncio.get_event_loop().time() + timeout
        decision = None
        while asyncio.get_event_loop().time() < deadline:
            val = await client.get(decision_key)
            if val:
                decision = val.decode() if isinstance(val, bytes) else str(val)
                await client.delete(decision_key)
                break
            await asyncio.sleep(0.4)
        await client.aclose()
    except Exception as e:  # noqa: BLE001
        log.warning("review_wait_failed", error=str(e))
        decision = None

    # Apply decision
    if decision == "DENY":
        state.verdict = Verdict.BLOCK
        state.block_reason = "denied_by_analyst"
        await _set_review_status(rid, "DENIED")
    elif decision == "APPROVE":
        state.verdict = Verdict.ALLOW
        await _set_review_status(rid, "APPROVED")
    else:
        # Timeout → auto-allow with audit trail
        state.verdict = Verdict.ALLOW
        await _set_review_status(rid, "TIMEOUT")
        state.audit_events.append({"agent": "review_queue", "decision": "timeout_auto_allow"})

    state.audit_events.append({"agent": "review_queue", "decision": state.verdict.value})
    await _publish_event(
        {
            "type": "review.decided",
            "request_id": rid,
            "decision": state.verdict.value,
        }
    )
    return state


async def _set_review_status(request_id: str, status: str) -> None:
    import datetime as dt

    from sqlalchemy import update

    try:
        async with SessionLocal() as db:
            await db.execute(
                update(ReviewQueueItem)
                .where(ReviewQueueItem.request_id == request_id)
                .values(status=status, decided_at=dt.datetime.now(dt.UTC))
            )
            await db.commit()
    except Exception as e:  # noqa: BLE001
        log.warning("review_status_update_failed", error=str(e))

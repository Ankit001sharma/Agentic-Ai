"""ContextBuilderAgent — loads user/session profile + risk tier from DB."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.core.logging import get_logger
from app.db.models import Session as SessionRow
from app.db.models import User
from app.db.session import SessionLocal
from app.schemas.sentinel import ScanState

log = get_logger("agent.context")


async def run(state: ScanState) -> ScanState:
    user_id = state.user.user_id
    session_id = state.user.session_id
    try:
        async with SessionLocal() as db:
            res = await db.execute(select(User).where(User.id == user_id))
            user = res.scalar_one_or_none()
            if user is None:
                user = User(id=user_id, tier=state.user.tier, region=state.user.region)
                db.add(user)
                await db.commit()
            else:
                state.user.tier = user.tier or state.user.tier
                state.user.region = user.region or state.user.region
                state.user.historical_risk = float(user.risk_score or 0.0)

            # Touch session
            sres = await db.execute(select(SessionRow).where(SessionRow.id == session_id))
            sess = sres.scalar_one_or_none()
            now = dt.datetime.now(dt.UTC)
            if sess is None:
                sess = SessionRow(id=session_id, user_id=user_id, started_at=now, last_seen_at=now, request_count=1)
                db.add(sess)
            else:
                sess.last_seen_at = now
                sess.request_count += 1
            await db.commit()
    except Exception as e:  # noqa: BLE001
        log.warning("context_builder_db_fail", error=str(e))

    state.audit_events.append(
        {
            "agent": "context_builder",
            "user": state.user.user_id,
            "tier": state.user.tier,
            "historical_risk": state.user.historical_risk,
            "session": state.user.session_id,
        }
    )
    return state

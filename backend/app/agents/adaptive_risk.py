"""AdaptiveRiskAgent — async post-response learning loop.

- Updates `users.risk_score` via EWMA based on the request's verdict.
- Inserts/updates `risk_graph_nodes` and `risk_graph_edges`.
- Mines simple patterns: if a user triggers >= 3 attacks in the last hour, propose
  a `suggested_policy` row for admin review.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.sql import func

from app.core.logging import get_logger
from app.db.models import Policy, Request, User
from app.db.risk_graph import upsert_edge, upsert_node
from app.db.session import SessionLocal
from app.schemas.sentinel import ScanState, Verdict

log = get_logger("agent.adaptive")

EWMA_ALPHA = 0.25


def _scalar_for_verdict(state: ScanState) -> float:
    if state.verdict == Verdict.BLOCK:
        return 1.0
    if state.verdict == Verdict.ESCALATE:
        return 0.8
    if state.verdict == Verdict.MASK:
        return 0.5
    return 0.0


async def run(state: ScanState) -> ScanState:
    """Background-safe agent: errors are swallowed to never block a response."""
    try:
        async with SessionLocal() as db:
            # 1) Update user EWMA risk score
            res = await db.execute(select(User).where(User.id == state.user.user_id))
            user = res.scalar_one_or_none()
            if user is None:
                user = User(id=state.user.user_id, tier=state.user.tier)
                db.add(user)
                await db.flush()
            scalar = _scalar_for_verdict(state)
            user.risk_score = float((1 - EWMA_ALPHA) * (user.risk_score or 0.0) + EWMA_ALPHA * scalar)
            user.attrs = {**(user.attrs or {}), "last_risk": state.risk}

            # 2) Risk graph upserts
            user_node = await upsert_node(
                db,
                node_type="user",
                key=state.user.user_id,
                score_delta=scalar,
                attrs={"tier": state.user.tier},
            )
            cats = sorted({f.category for f in state.findings})
            for cat in cats:
                cat_node = await upsert_node(
                    db, node_type="category", key=cat, score_delta=1.0
                )
                await upsert_edge(db, user_node.id, cat_node.id, kind="triggered", weight_delta=1.0)

            # 3) Mine pattern: >=3 attacks in last hour by this user => suggest policy
            since = dt.datetime.now(dt.UTC) - dt.timedelta(hours=1)
            count_res = await db.execute(
                select(func.count(Request.id)).where(
                    Request.user_id == state.user.user_id,
                    Request.created_at >= since,
                    Request.verdict.in_(["BLOCK", "ESCALATE"]),
                )
            )
            recent = int(count_res.scalar() or 0)
            if recent >= 3:
                name = f"auto_block_user_{state.user.user_id}"
                exists = await db.execute(select(Policy).where(Policy.name == name))
                if exists.scalar_one_or_none() is None:
                    db.add(
                        Policy(
                            name=name,
                            rego=(
                                f'package sentinel\n\nallow := false {{ input.user.id == "{state.user.user_id}" }}\n'
                            ),
                            enabled=False,
                            suggested=True,
                            suggested_by="adaptive_risk_agent",
                            suggested_reason=(
                                f"User {state.user.user_id} produced {recent} BLOCK/ESCALATE in 1h"
                            ),
                            approved=False,
                        )
                    )

            await db.commit()
    except Exception as e:  # noqa: BLE001
        log.warning("adaptive_risk_failed", error=str(e))
    return state

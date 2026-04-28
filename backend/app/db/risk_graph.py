"""Helpers to upsert nodes/edges in the Risk Graph."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RiskGraphEdge, RiskGraphNode


async def upsert_node(
    session: AsyncSession,
    node_type: str,
    key: str,
    score_delta: float = 0.0,
    attrs: dict | None = None,
) -> RiskGraphNode:
    stmt = select(RiskGraphNode).where(
        RiskGraphNode.node_type == node_type, RiskGraphNode.key == key
    )
    res = await session.execute(stmt)
    node = res.scalar_one_or_none()
    if node is None:
        node = RiskGraphNode(node_type=node_type, key=key, score=score_delta, attrs=attrs or {})
        session.add(node)
        await session.flush()
    else:
        node.score = float(node.score) + score_delta
        if attrs:
            merged = dict(node.attrs or {})
            merged.update(attrs)
            node.attrs = merged
        node.updated_at = dt.datetime.now(dt.UTC)
    return node


async def upsert_edge(
    session: AsyncSession, src_id: int, dst_id: int, kind: str, weight_delta: float = 1.0
) -> RiskGraphEdge:
    stmt = select(RiskGraphEdge).where(
        RiskGraphEdge.src == src_id,
        RiskGraphEdge.dst == dst_id,
        RiskGraphEdge.kind == kind,
    )
    res = await session.execute(stmt)
    edge = res.scalar_one_or_none()
    if edge is None:
        edge = RiskGraphEdge(src=src_id, dst=dst_id, kind=kind, weight=weight_delta)
        session.add(edge)
        await session.flush()
    else:
        edge.weight = float(edge.weight) + weight_delta
        edge.updated_at = dt.datetime.now(dt.UTC)
    return edge

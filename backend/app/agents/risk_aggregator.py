"""RiskAggregatorAgent — 0..100 weighted aggregation."""

from __future__ import annotations

from app.core.risk import effective_risk_breakdown
from app.schemas.sentinel import ScanState


async def run(state: ScanState) -> ScanState:
    score, breakdown = effective_risk_breakdown(state)
    state.risk = score
    state.risk_breakdown = breakdown
    state.audit_events.append({"agent": "risk_aggregator", "risk": score, "breakdown": breakdown})
    return state

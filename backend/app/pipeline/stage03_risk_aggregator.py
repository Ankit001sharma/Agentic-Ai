"""Stage 3 — Risk Aggregator.

Computes weighted 0–100 risk score from all findings plus historical risk.
Stores score and per-category breakdown on the state.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.core.risk import aggregate
from app.pipeline.base import Stage
from app.schemas.sentinel import ScanState

log = get_logger("pipeline.stage03")


class RiskAggregatorStage(Stage):
    async def run(self, state: ScanState) -> ScanState:
        state.pipeline_stage = 3
        score, breakdown = aggregate(
            state.findings,
            historical_risk=state.user.historical_risk,
        )
        state.risk = score
        state.risk_breakdown = breakdown
        log.info(
            "stage03_done",
            request_id=state.request_id,
            risk=score,
            categories=list(breakdown.keys()),
        )
        return state

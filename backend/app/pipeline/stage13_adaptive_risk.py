"""Stage 13 — Adaptive Risk Update.

Updates the user's risk profile in Postgres based on the outcome of this
request.  A BLOCK or high-risk execution nudges the score upward; clean
executions allow it to decay.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.pipeline.base import Stage
from app.schemas.sentinel import ScanState, Verdict

log = get_logger("pipeline.stage13")

# How much to shift user historical_risk per verdict outcome (fractional 0–1)
_DELTA: dict[str, float] = {
    Verdict.BLOCK.value: 0.10,
    Verdict.MASK.value: 0.02,
    Verdict.ALLOW.value: -0.005,   # small decay on clean requests
    Verdict.ESCALATE.value: 0.05,
}
_CLAMP_MAX = 1.0
_CLAMP_MIN = 0.0


class AdaptiveRiskStage(Stage):
    async def run(self, state: ScanState) -> ScanState:
        state.pipeline_stage = 13

        if state.user.user_id == "anonymous":
            return state

        delta = _DELTA.get(state.verdict.value, 0.0)
        old_risk = state.user.historical_risk
        new_risk = max(_CLAMP_MIN, min(_CLAMP_MAX, old_risk + delta))

        if abs(new_risk - old_risk) < 1e-6:
            return state

        try:
            from app.db.session import SessionLocal
            from sqlalchemy import text

            async with SessionLocal() as session:
                await session.execute(
                    text(
                        """
                        INSERT INTO user_risk (user_id, risk_score, updated_at)
                        VALUES (:user_id, :score, now())
                        ON CONFLICT (user_id) DO UPDATE
                          SET risk_score = :score,
                              updated_at = now()
                        """
                    ),
                    {"user_id": state.user.user_id, "score": new_risk},
                )
                await session.commit()

            log.info(
                "stage13_done",
                user_id=state.user.user_id,
                old_risk=old_risk,
                new_risk=new_risk,
                verdict=state.verdict.value,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("stage13_db_error", error=str(exc))

        return state

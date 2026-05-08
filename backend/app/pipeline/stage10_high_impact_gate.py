"""Stage 10 — High-Impact Gate.

REQUIRED when ANY of the following is true:
  • tool definition has high_impact=true  (external recipients, destructive ops)
  • Stage 8 set external=true in tool_args  (email/SMS to non-internal domain)
  • Stage 8 set requires_confirmation=true  (destructive: delete, merge, refund)

Writes the review request to Redis and polls for a human decision within the
configured timeout.

Decision outcomes:
  "approved"  → pipeline continues
  "rejected"  → BLOCK
  "timeout"   → BLOCK (default safe)
"""

from __future__ import annotations

import asyncio
import json
import time

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.pipeline.base import Stage
from app.schemas.sentinel import ScanState, Verdict

log = get_logger("pipeline.stage10")

_REVIEW_QUEUE_KEY = "pipeline:high_impact_review"
_REVIEW_RESULT_PREFIX = "pipeline:review_result:"


class HighImpactGateStage(Stage):
    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client

    async def run(self, state: ScanState) -> ScanState:
        state.pipeline_stage = 10
        s = get_settings()

        if state.verdict == Verdict.BLOCK:
            return state

        # Determine whether this call needs human review.
        # Three independent triggers (any one is sufficient):
        #   1. Tool definition marks it high_impact (set at Stage 6)
        #   2. Nemotron put external:true in the generated args (Stage 8)
        #   3. Nemotron put requires_confirmation:true in the generated args (Stage 8)
        needs_review = (
            state.high_impact
            or state.fn_call_external
            or state.fn_call_requires_confirmation
        )

        if not needs_review or not state.tool_id:
            return state

        # Annotate why review was triggered for the reviewer UI
        trigger_reasons: list[str] = []
        if state.high_impact:
            trigger_reasons.append("tool marked high_impact")
        if state.fn_call_external:
            trigger_reasons.append("external recipient detected")
        if state.fn_call_requires_confirmation:
            trigger_reasons.append("destructive action requires confirmation")

        state.human_review_required = True
        review_id = state.request_id
        timeout = s.high_impact_review_timeout

        review_payload = {
            "review_id": review_id,
            "request_id": state.request_id,
            "user_id": state.user.user_id,
            "tool_id": state.tool_id,
            "intent": state.intent,
            "trigger_reasons": trigger_reasons,
            "rationale": state.tool_args_rationale or "",
            "tool_args_preview": _safe_preview(state.tool_args),
            "risk": state.risk,
            "submitted_at": time.time(),
            "expires_at": time.time() + timeout,
        }

        # Push review request to queue
        await self._redis.lpush(
            _REVIEW_QUEUE_KEY,
            json.dumps(review_payload),
        )
        log.info(
            "stage10_review_queued",
            request_id=state.request_id,
            tool_id=state.tool_id,
            triggers=trigger_reasons,
            timeout=timeout,
        )

        # Poll for decision
        result_key = f"{_REVIEW_RESULT_PREFIX}{review_id}"
        decision = await self._poll_decision(result_key, timeout)

        state.human_review_decision = decision
        # The review has now resolved (approved/rejected/timeout); flip the
        # gate flag back to False so dashboards/audit tooling don't keep
        # treating this request as "still pending review".
        state.human_review_required = False

        if decision == "approved":
            log.info("stage10_approved", request_id=state.request_id)
        else:
            state.verdict = Verdict.BLOCK
            state.block_reason = (
                f"High-impact tool '{state.tool_id}' "
                + ("rejected by reviewer." if decision == "rejected" else "timed out awaiting review.")
            )
            log.warning(
                "stage10_blocked",
                request_id=state.request_id,
                decision=decision,
            )

        return state

    async def _poll_decision(self, result_key: str, timeout: int) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            raw = await self._redis.get(result_key)
            if raw:
                await self._redis.delete(result_key)
                data = json.loads(raw)
                return data.get("decision", "timeout")
            await asyncio.sleep(2)
        return "timeout"


def _safe_preview(args: dict) -> dict:
    """Return a truncated preview of args (no raw secrets)."""
    preview: dict = {}
    for k, v in args.items():
        if isinstance(v, str):
            preview[k] = v[:100] + ("…" if len(v) > 100 else "")
        elif isinstance(v, list):
            preview[k] = [str(i)[:50] for i in v[:5]]
        else:
            preview[k] = v
    return preview

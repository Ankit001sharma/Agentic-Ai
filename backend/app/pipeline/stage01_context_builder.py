"""Stage 1 — Context Builder.

Loads user profile, session risk, and recent STM turns from Redis.
Populates state.stm_context before any scanning begins.
"""

from __future__ import annotations

import redis.asyncio as aioredis

from app.core.logging import get_logger
from app.memory.stm import ShortTermMemory
from app.pipeline.base import Stage
from app.schemas.sentinel import ScanState

log = get_logger("pipeline.stage01")


class ContextBuilderStage(Stage):
    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._stm = ShortTermMemory(redis_client)

    async def run(self, state: ScanState) -> ScanState:
        state.pipeline_stage = 1

        # Load STM snapshot for this conversation
        if state.conv_id and state.user.user_id != "anonymous":
            ctx = await self._stm.load(state.user.user_id, state.conv_id)
            state.stm_context = ctx
            log.info(
                "stm_loaded",
                user_id=state.user.user_id,
                conv_id=state.conv_id,
                turns=len(ctx.get("turns", [])),
            )
        else:
            state.stm_context = {}

        # Persist the incoming user turn to STM. We DO await this — losing
        # a user turn would break pronoun resolution in Stage 5 and the
        # conversation-history injection in Stage 14. Stage 5 will append
        # the intent shortly after.
        if state.user.user_id != "anonymous":
            await self._stm.add_turn(
                state.user.user_id,
                state.conv_id,
                "user",
                state.prompt,
            )

        log.info(
            "stage01_done",
            request_id=state.request_id,
            historical_risk=state.user.historical_risk,
        )
        return state

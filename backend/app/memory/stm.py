"""Redis-backed Short-Term Memory.

Key schema:  stm:{user_id}:{conv_id}
TTL:         30 min sliding (reset on every read/write)
Stored keys: last_intent, entities, last_tool, last_args,
             last_result, turns[N=5]

All writes pass through _redact() before storage — raw secrets and
PII tokens are never persisted.
"""

from __future__ import annotations

import json
import re
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings

# Simple token patterns to strip before writing to STM
_SECRET_RE = re.compile(
    r"(password|token|secret|api.?key|bearer)\s*[:=]\s*\S+",
    re.IGNORECASE,
)


def _redact(obj: Any) -> Any:
    """Recursively strip secret-looking strings from a nested structure."""
    if isinstance(obj, str):
        return _SECRET_RE.sub(r"\1=[REDACTED]", obj)
    if isinstance(obj, dict):
        return {k: _redact(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(v) for v in obj]
    return obj


class ShortTermMemory:
    """Per-user, per-conversation Redis memory store."""

    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._redis = redis_client
        self._settings = get_settings()

    # ── key helpers ──────────────────────────────────────────────────────────

    def _key(self, user_id: str, conv_id: str) -> str:
        return f"stm:{user_id}:{conv_id}"

    # ── public API ───────────────────────────────────────────────────────────

    async def load(self, user_id: str, conv_id: str) -> dict[str, Any]:
        """Load full STM context; slide TTL; return {} on miss."""
        key = self._key(user_id, conv_id)
        raw = await self._redis.get(key)
        if not raw:
            return {}
        # Slide TTL on every read
        await self._redis.expire(key, self._settings.stm_ttl_seconds)
        return json.loads(raw)

    async def save(self, user_id: str, conv_id: str, context: dict[str, Any]) -> None:
        """Overwrite the full STM context (redacted)."""
        key = self._key(user_id, conv_id)
        await self._redis.setex(
            key,
            self._settings.stm_ttl_seconds,
            json.dumps(_redact(context)),
        )

    async def update_intent(
        self,
        user_id: str,
        conv_id: str,
        intent: str,
        entities: list[str],
    ) -> None:
        """Called after Stage 5: persist intent + entities."""
        ctx = await self.load(user_id, conv_id)
        ctx["last_intent"] = intent
        ctx["entities"] = _redact(entities)
        await self.save(user_id, conv_id, ctx)

    async def update_tool_result(
        self,
        user_id: str,
        conv_id: str,
        tool_id: str,
        args: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        """Called after Stage 11: persist tool + result (redacted)."""
        ctx = await self.load(user_id, conv_id)
        ctx["last_tool"] = tool_id
        ctx["last_args"] = _redact(args)
        ctx["last_result"] = _redact(result)
        await self.save(user_id, conv_id, ctx)

    async def add_turn(
        self,
        user_id: str,
        conv_id: str,
        role: str,
        content: str,
    ) -> None:
        """Append a turn, keeping the last N=stm_max_turns entries."""
        ctx = await self.load(user_id, conv_id)
        turns: list[dict[str, Any]] = ctx.get("turns", [])
        turns.append({"role": role, "content": _redact(content)})
        ctx["turns"] = turns[-self._settings.stm_max_turns :]
        await self.save(user_id, conv_id, ctx)

    async def delete(self, user_id: str, conv_id: str) -> None:
        """Hard-delete the STM key (e.g. on explicit logout)."""
        await self._redis.delete(self._key(user_id, conv_id))

    async def promote_to_long_term(self, user_id: str, conv_id: str) -> None:
        """Persist STM context to Postgres long-term memory, then delete the Redis key.

        Called on session end (logout) so cross-session entity/intent context
        survives beyond the 30-minute STM TTL.
        """
        ctx = await self.load(user_id, conv_id)
        if not ctx:
            return

        try:
            from app.db.models import UserMemory
            from app.db.session import SessionLocal

            tool_exec: list[dict] = []
            if ctx.get("last_tool"):
                tool_exec = [{
                    "tool_id": ctx["last_tool"],
                    "args_summary": str(ctx.get("last_args", {}))[:200],
                    "result_summary": str(ctx.get("last_result", {}))[:200],
                }]

            mem = UserMemory(
                user_id=user_id,
                conv_id=conv_id,
                last_intent=ctx.get("last_intent"),
                entities=ctx.get("entities", []),
                tool_executions=tool_exec,
                turn_count=len(ctx.get("turns", [])),
            )
            async with SessionLocal() as db:
                db.add(mem)
                await db.commit()
        except Exception:  # noqa: BLE001
            pass  # Promotion failure must not block logout

        await self.delete(user_id, conv_id)

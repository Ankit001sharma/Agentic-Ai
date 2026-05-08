"""Slack tool executor via Slack Web API."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.tools.base import ToolExecutor, ToolResult

log = get_logger("tools.slack")

SLACK_POST_MESSAGE = "https://slack.com/api/chat.postMessage"


class SlackToolExecutor(ToolExecutor):
    """Posts messages to Slack channels or DMs."""

    async def execute(
        self,
        args: dict[str, Any],
        *,
        idempotency_key: str,
        simulate: bool = False,
    ) -> ToolResult:
        s = get_settings()
        channel: str = args.get("channel", "")
        text: str = args.get("text", "")
        blocks: list[Any] | None = args.get("blocks")

        if simulate or args.get("simulate"):
            log.info("slack_simulate", channel=channel, idempotency_key=idempotency_key)
            return ToolResult.ok(
                "send_slack_message",
                {"simulated": True, "channel": channel, "text": text[:100]},
                simulated=True,
                idempotency_key=idempotency_key,
            )

        if not s.slack_bot_token:
            return ToolResult.fail(
                "send_slack_message",
                code="TOOL_CONFIG_ERROR",
                message="SLACK_BOT_TOKEN is not configured",
                retryable=False,
                user_facing=True,
                idempotency_key=idempotency_key,
            )

        payload: dict[str, Any] = {"channel": channel, "text": text}
        if blocks:
            payload["blocks"] = blocks

        headers = {
            "Authorization": f"Bearer {s.slack_bot_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        try:
            async with httpx.AsyncClient(timeout=s.tool_slack_timeout) as client:
                resp = await asyncio.wait_for(
                    client.post(SLACK_POST_MESSAGE, json=payload, headers=headers),
                    timeout=s.tool_slack_timeout,
                )
            data = resp.json()
            if data.get("ok"):
                log.info("slack_sent", channel=channel, ts=data.get("ts"))
                return ToolResult.ok(
                    "send_slack_message",
                    {"channel": data.get("channel"), "ts": data.get("ts")},
                    idempotency_key=idempotency_key,
                )
            error_code = data.get("error", "unknown_error")
            return ToolResult.fail(
                "send_slack_message",
                code=f"SLACK_{error_code.upper()}",
                message=error_code,
                retryable=error_code in ("rate_limited", "service_unavailable"),
                user_facing=True,
                idempotency_key=idempotency_key,
            )
        except (httpx.TimeoutException, asyncio.TimeoutError):
            return ToolResult.fail(
                "send_slack_message",
                code="TOOL_TIMEOUT",
                message="Slack API timed out",
                retryable=True,
                user_facing=True,
                idempotency_key=idempotency_key,
            )

"""Email tool executor via Resend API."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.tools.base import ToolExecutor, ToolResult

log = get_logger("tools.email")


class EmailToolExecutor(ToolExecutor):
    """Sends transactional email via the Resend REST API."""

    RESEND_API_URL = "https://api.resend.com/emails"

    async def execute(
        self,
        args: dict[str, Any],
        *,
        idempotency_key: str,
        simulate: bool = False,
    ) -> ToolResult:
        s = get_settings()
        to_list: list[str] = args.get("to", [])
        subject: str = args.get("subject", "")
        body: str = args.get("body", "")
        cc_list: list[str] = args.get("cc", [])

        if simulate or args.get("simulate"):
            log.info("email_simulate", to=to_list, subject=subject, idempotency_key=idempotency_key)
            return ToolResult.ok(
                "send_email",
                {"simulated": True, "to": to_list, "subject": subject},
                simulated=True,
                idempotency_key=idempotency_key,
            )

        if not s.resend_api_key:
            return ToolResult.fail(
                "send_email",
                code="TOOL_CONFIG_ERROR",
                message="RESEND_API_KEY is not configured",
                retryable=False,
                user_facing=True,
                idempotency_key=idempotency_key,
            )

        payload: dict[str, Any] = {
            "from": s.resend_from_email,
            "to": to_list,
            "subject": subject,
            "text": body,
        }
        if cc_list:
            payload["cc"] = cc_list

        headers = {
            "Authorization": f"Bearer {s.resend_api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
        }

        try:
            async with httpx.AsyncClient(timeout=s.tool_email_timeout) as client:
                resp = await asyncio.wait_for(
                    client.post(self.RESEND_API_URL, json=payload, headers=headers),
                    timeout=s.tool_email_timeout,
                )
            if resp.status_code in (200, 201):
                data = resp.json()
                log.info("email_sent", message_id=data.get("id"), to=to_list)
                return ToolResult.ok(
                    "send_email",
                    {"message_id": data.get("id"), "to": to_list, "subject": subject},
                    idempotency_key=idempotency_key,
                )
            return ToolResult.fail(
                "send_email",
                code=f"RESEND_HTTP_{resp.status_code}",
                message=resp.text[:500],
                retryable=resp.status_code >= 500,
                user_facing=True,
                idempotency_key=idempotency_key,
            )
        except (httpx.TimeoutException, asyncio.TimeoutError):
            return ToolResult.fail(
                "send_email",
                code="TOOL_TIMEOUT",
                message="Resend API timed out",
                retryable=True,
                user_facing=True,
                idempotency_key=idempotency_key,
            )

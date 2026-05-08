"""Base classes and result types for all tool executors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ToolResult(BaseModel):
    """Structured result returned by every tool executor."""

    tool_id: str
    success: bool
    data: dict[str, Any] = {}
    error: dict[str, Any] | None = None
    simulated: bool = False
    idempotency_key: str = ""

    @classmethod
    def ok(
        cls,
        tool_id: str,
        data: dict[str, Any],
        *,
        simulated: bool = False,
        idempotency_key: str = "",
    ) -> "ToolResult":
        return cls(
            tool_id=tool_id,
            success=True,
            data=data,
            simulated=simulated,
            idempotency_key=idempotency_key,
        )

    @classmethod
    def fail(
        cls,
        tool_id: str,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        user_facing: bool = True,
        idempotency_key: str = "",
    ) -> "ToolResult":
        return cls(
            tool_id=tool_id,
            success=False,
            error={
                "code": code,
                "message": message,
                "retryable": retryable,
                "user_facing": user_facing,
            },
            idempotency_key=idempotency_key,
        )


class ToolExecutor(ABC):
    """Every tool executor must implement execute()."""

    @abstractmethod
    async def execute(
        self,
        args: dict[str, Any],
        *,
        idempotency_key: str,
        simulate: bool = False,
    ) -> ToolResult:
        ...

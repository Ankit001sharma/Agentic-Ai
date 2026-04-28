"""Tool execution result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    ok: bool
    name: str
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    latency_ms: int = 0
    error: str | None = None

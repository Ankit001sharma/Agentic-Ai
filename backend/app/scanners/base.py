"""Common scanner protocol + result type."""

from __future__ import annotations

from typing import Protocol

from app.schemas.sentinel import Finding


class ScannerResult:
    __slots__ = ("findings", "score")

    def __init__(self, findings: list[Finding] | None = None, score: float = 0.0) -> None:
        self.findings: list[Finding] = findings or []
        self.score: float = max(0.0, min(1.0, float(score)))


class Scanner(Protocol):
    name: str

    async def scan(self, text: str, **ctx) -> ScannerResult: ...

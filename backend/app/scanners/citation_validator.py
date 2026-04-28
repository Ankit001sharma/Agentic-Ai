"""Output scanner — citation / URL validity check.

If a response contains URLs or DOIs we issue HEAD requests with a tight timeout
to verify they exist; broken citations are flagged HALLUCINATION.
"""

from __future__ import annotations

import asyncio
import re

import httpx

from app.schemas.sentinel import Finding

from .base import ScannerResult

URL_RE = re.compile(r"https?://[^\s)\]\"<>]+")
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)


class CitationValidator:
    name = "citation_validator"
    TIMEOUT = 2.0
    MAX_URLS = 4

    async def scan(self, text: str, **_ctx) -> ScannerResult:
        if not text:
            return ScannerResult()
        urls = URL_RE.findall(text)[: self.MAX_URLS]
        if not urls:
            return ScannerResult()

        async def check(u: str) -> tuple[str, bool]:
            try:
                async with httpx.AsyncClient(timeout=self.TIMEOUT, follow_redirects=True) as c:
                    r = await c.head(u)
                    return u, 200 <= r.status_code < 400
            except Exception:  # noqa: BLE001
                return u, False

        results = await asyncio.gather(*(check(u) for u in urls), return_exceptions=False)
        broken = [u for u, ok in results if not ok]
        if not broken:
            return ScannerResult()
        sev = min(1.0, 0.4 + 0.15 * len(broken))
        return ScannerResult(
            findings=[
                Finding(
                    category="HALLUCINATION",
                    scanner=self.name,
                    severity=sev,
                    evidence=f"broken citations: {', '.join(broken[:2])}",
                    metadata={"broken": broken, "checked": [u for u, _ in results]},
                )
            ],
            score=sev,
        )

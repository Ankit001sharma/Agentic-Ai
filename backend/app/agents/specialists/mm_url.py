"""URLThreatAgent — URLs in prompt + attachment URLs with lightweight reputation stub."""

from __future__ import annotations

import re

from app.schemas.explanation import AgentFindingRecord
from app.agents.specialists.base import append_finding
from app.schemas.sentinel import ScanState

_URL = re.compile(r"https?://[^\s)<>'\"]+", re.IGNORECASE)

# Stub denylist / suspicious TLDs for defensive routing hints
_SHADY = ("bit.ly", "tinyurl.com", "pastebin.com", "telegram.me", ".onion")


async def analyze_prompt_and_attachments(state: ScanState) -> None:
    text = state.prompt or ""
    urls = _URL.findall(text)
    for att in state.attachments:
        u = att.get("url")
        if isinstance(u, str) and u.startswith("http"):
            urls.append(u)
    if not urls:
        return
    issues: list[str] = []
    for u in urls[:16]:
        lu = u.lower()
        if any(s in lu for s in _SHADY):
            issues.append(f"suspicious_host:{u[:80]}")
    append_finding(
        state,
        AgentFindingRecord(
            agent="url_threat",
            claim="url_reputation_stub",
            evidence=issues or [f"urls_count:{len(urls)}"],
            confidence=0.55 if issues else 0.35,
            metadata={"urls_seen": len(urls)},
        ),
    )

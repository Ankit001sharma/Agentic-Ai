"""Output policy violation scanner — checks the response against an OPA policy
(or, in fallback mode, a configurable banned-phrase list)."""

from __future__ import annotations

import re

from app.schemas.sentinel import Finding

from .base import ScannerResult

# Demo banned phrase list — illustrative. In practice these come from OPA / config.
_BANNED = [
    (re.compile(r"(?i)\bcompetitor\s+(corp|inc|llc)\b"), "competitor mention"),
    (re.compile(r"(?i)\b(insider\s+trading|illegal\s+activity)\b"), "illegal activity"),
    (re.compile(r"(?i)\bbomb[-\s]?making\b"), "weapons content"),
]


class PolicyViolationScanner:
    name = "policy_violation"

    async def scan(self, text: str, **_ctx) -> ScannerResult:
        if not text:
            return ScannerResult()
        findings: list[Finding] = []
        max_sev = 0.0
        for pat, label in _BANNED:
            m = pat.search(text)
            if m:
                sev = 0.8
                max_sev = max(max_sev, sev)
                findings.append(
                    Finding(
                        category="POLICY_VIOLATION",
                        scanner=self.name,
                        severity=sev,
                        evidence=m.group(0)[:80],
                        metadata={"policy": label},
                    )
                )
        return ScannerResult(findings=findings, score=max_sev)

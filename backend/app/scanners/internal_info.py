"""InternalInfoScanner — flags prompts that ask for *internal company information*
where the model has no grounded source.  This is the input-side complement to the
citation_validator output scanner.

Emits UNVERIFIED_INTERNAL findings; aggregator treats it like a HALLUCINATION risk.
"""

from __future__ import annotations

import re

from app.schemas.sentinel import Finding

from .base import ScannerResult

# Trigger phrases that suggest the user is asking the LLM to reveal/produce internal
# enterprise knowledge (which it cannot reliably know).
# Allow up to ~40 chars between the possessive ("our", "our company's") and the protected
# noun (revenue, roadmap, etc.) so phrases like "our company's Q4 revenue" still match.
_GAP = r".{0,40}?\b"

_INTERNAL_PATTERNS: list[tuple[str, str, float]] = [
    ("internal_doc", r"(?i)\b(our|the\s+company(?:'s)?|internal)\b" + _GAP + r"(roadmap|policy|wiki|playbook|runbook|sops?|design\s+docs?|architecture)\b", 0.6),
    ("financials", r"(?i)\b(our|the\s+company(?:'s)?)\b" + _GAP + r"(revenue|arr|mrr|earnings|profit|p&l|forecast|budget)\b", 0.75),
    ("employees", r"(?i)\b(employee|staff)\s+(list|directory|salaries|reviews|records?)", 0.8),
    ("clients", r"(?i)\b(our|company)\b" + _GAP + r"(client|customer|account)\s+(list|records?)", 0.8),
    ("incident", r"(?i)\b(internal|production)\s+(incident|outage|postmortem)\s+(report|details)?", 0.7),
    ("contract", r"(?i)\b(our|company)\s+(contract|nda|msa)\s+terms?", 0.7),
    ("source_code", r"(?i)\b(our|internal|proprietary)\s+source\s+code\b", 0.75),
    ("knowledge_base", r"(?i)\b(internal\s+knowledge\s+base|internal\s+wiki|confluence\s+space)\b", 0.55),
    ("project_codename", r"(?i)\binternal\s+(project|codename|product\s+roadmap)\b", 0.6),
]


class InternalInfoScanner:
    name = "internal_info"

    def __init__(self) -> None:
        self._patterns = [(label, re.compile(pat), sev) for label, pat, sev in _INTERNAL_PATTERNS]

    async def scan(self, text: str, **_ctx) -> ScannerResult:
        if not text:
            return ScannerResult()
        findings: list[Finding] = []
        max_sev = 0.0
        for label, pat, sev in self._patterns:
            m = pat.search(text)
            if m:
                max_sev = max(max_sev, sev)
                findings.append(
                    Finding(
                        category="UNVERIFIED_INTERNAL",
                        scanner=self.name,
                        severity=sev,
                        evidence=m.group(0)[:80],
                        metadata={"trigger": label},
                    )
                )
        return ScannerResult(findings=findings, score=max_sev)

"""Dangerous-instruction detector (for output side).

Catches shell / SQL / OS-level destructive patterns and unsafe code constructs the
LLM may have hallucinated.
"""

from __future__ import annotations

import re

from app.schemas.sentinel import Finding

from .base import ScannerResult

_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    ("rm_rf_root", re.compile(r"\brm\s+-rf\s+/(?:\s|$)"), 1.0),
    ("rm_rf_home", re.compile(r"\brm\s+-rf\s+(\$HOME|~)"), 0.95),
    ("dd_zero", re.compile(r"\bdd\s+if=/dev/zero\s+of=/dev/[a-z]+"), 1.0),
    ("mkfs", re.compile(r"\bmkfs(\.[a-z0-9]+)?\s+/dev/"), 0.95),
    ("forkbomb", re.compile(r":\(\)\{\s*:\|:&\s*\};:"), 1.0),
    ("drop_database", re.compile(r"\bDROP\s+(DATABASE|SCHEMA|TABLE)\s+", re.I), 0.85),
    ("truncate_table", re.compile(r"\bTRUNCATE\s+TABLE\s+", re.I), 0.7),
    ("os_system_rm", re.compile(r"os\.system\s*\(\s*['\"][^'\"]*\brm\s+-rf\b"), 1.0),
    ("subprocess_shell", re.compile(r"subprocess\.(call|run|Popen)\s*\([^)]*shell\s*=\s*True", re.I), 0.55),
    ("eval_input", re.compile(r"\beval\s*\(\s*input\s*\(", re.I), 0.7),
    ("powershell_iex", re.compile(r"(?i)powershell.*-(EncodedCommand|enc)\s+", re.I), 0.85),
    ("curl_pipe_sh", re.compile(r"\bcurl\s+[^|]+\|\s*(sudo\s+)?(bash|sh)\b"), 0.9),
    ("wget_pipe_sh", re.compile(r"\bwget\s+[^|]+\|\s*(sudo\s+)?(bash|sh)\b"), 0.9),
    ("chmod_777", re.compile(r"\bchmod\s+0?777\b"), 0.45),
]


class DangerousCodeScanner:
    name = "dangerous_code"

    async def scan(self, text: str, **_ctx) -> ScannerResult:
        if not text:
            return ScannerResult()
        findings: list[Finding] = []
        max_sev = 0.0
        for label, pat, sev in _PATTERNS:
            m = pat.search(text)
            if m:
                max_sev = max(max_sev, sev)
                findings.append(
                    Finding(
                        category="DANGEROUS_CODE",
                        scanner=self.name,
                        severity=sev,
                        evidence=m.group(0)[:120],
                        metadata={"rule": label},
                    )
                )
        return ScannerResult(findings=findings, score=max_sev)

"""Code / IP detector — looks for proprietary code markers, internal package names,
copyright headers, license blocks.  Fast pure-regex implementation."""

from __future__ import annotations

import re

from app.schemas.sentinel import Finding

from .base import ScannerResult

_PATTERNS: list[tuple[str, re.Pattern[str], float, str]] = [
    (
        "CopyrightHeader",
        re.compile(r"(?i)copyright\s*\(c\)\s*\d{4}", re.I),
        0.55,
        "Copyright header",
    ),
    (
        "ProprietaryBanner",
        re.compile(r"(?i)\b(proprietary|confidential)\s+(and\s+)?(trade\s+secret|do\s+not\s+distribute|internal\s+use\s+only)", re.I),
        0.85,
        "Proprietary / Confidential banner",
    ),
    (
        "InternalImport",
        re.compile(r"(?i)\b(from|import)\s+(acme_internal|company_internal|internal\.|corp_internal)[A-Za-z_.\d]*", re.I),
        0.75,
        "Internal-package import",
    ),
    (
        "LicensedCode",
        re.compile(r"(?i)\b(GPL|AGPL|MIT|Apache)\s+(License|Licensed)", re.I),
        0.25,
        "License reference",
    ),
    (
        "ConnectionString",
        re.compile(r"(?i)\b(jdbc|mongodb|postgres(ql)?|mysql|redis):\/\/[^\s]+:[^\s]+@", re.I),
        0.95,
        "Embedded connection string with credentials",
    ),
    (
        "PrivateRepoUrl",
        re.compile(r"(?i)\b(git@|https:\/\/)(github|gitlab|bitbucket)\.[A-Za-z0-9.\-]+(:|\/)[A-Za-z0-9._\-\/]+\.git", re.I),
        0.45,
        "Internal repo URL",
    ),
]


class CodeIPScanner:
    name = "code_ip"

    async def scan(self, text: str, **_ctx) -> ScannerResult:
        if not text:
            return ScannerResult()
        findings: list[Finding] = []
        max_sev = 0.0
        for label, pat, sev, desc in _PATTERNS:
            m = pat.search(text)
            if m:
                max_sev = max(max_sev, sev)
                findings.append(
                    Finding(
                        category="CODE_IP",
                        scanner=self.name,
                        severity=sev,
                        evidence=m.group(0)[:80],
                        metadata={"type": label, "description": desc},
                    )
                )
        return ScannerResult(findings=findings, score=max_sev)

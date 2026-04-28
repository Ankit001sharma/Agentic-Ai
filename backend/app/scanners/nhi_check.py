"""NHIScanner — Non-Human Identity / Service-auth validation.

Inspects who the caller claims to be (X-Auth-Type header → user.auth_type) and
flags suspicious patterns such as:
- service/bot identity making a privacy-sensitive or escalation-style request
- bot identity exhibiting human-only behaviour patterns (e.g. asking for free-form
  emotional advice) — soft signal
- missing/unknown auth_type performing high-risk actions

Emits NHI_VIOLATION findings.
"""

from __future__ import annotations

import re

from app.schemas.sentinel import Finding

from .base import ScannerResult

_HUMAN_LIKE = re.compile(
    r"(?i)\b(my\s+(feelings?|partner|family|child|kid)|i\s+feel|i'?m\s+(sad|anxious|depressed))\b"
)
_PRIVILEGED = re.compile(
    r"(?i)\b(disable|delete|drop|grant\s+admin|approve\s+(payment|payout)|wire\s+funds)\b"
)


class NHIScanner:
    name = "nhi_check"

    async def scan(self, text: str, **ctx) -> ScannerResult:
        auth_type = (ctx.get("auth_type") or "human").lower()
        findings: list[Finding] = []
        max_sev = 0.0

        # Service/bot performing privileged actions without admin role is suspicious.
        role = (ctx.get("role") or "viewer").lower()
        if auth_type in ("service", "bot") and _PRIVILEGED.search(text or "") and role != "admin":
            sev = 0.8
            max_sev = max(max_sev, sev)
            findings.append(
                Finding(
                    category="NHI_VIOLATION",
                    scanner=self.name,
                    severity=sev,
                    evidence="service/bot requesting privileged action without admin role",
                    metadata={"auth_type": auth_type, "role": role},
                )
            )

        # Bot/service producing very human-looking emotional content -> soft anomaly
        if auth_type in ("service", "bot") and _HUMAN_LIKE.search(text or ""):
            sev = 0.4
            max_sev = max(max_sev, sev)
            findings.append(
                Finding(
                    category="NHI_VIOLATION",
                    scanner=self.name,
                    severity=sev,
                    evidence="non-human identity producing human-style content",
                    metadata={"auth_type": auth_type},
                )
            )

        # Unknown auth_type doing privileged things
        if auth_type not in ("human", "bot", "service") and _PRIVILEGED.search(text or ""):
            sev = 0.65
            max_sev = max(max_sev, sev)
            findings.append(
                Finding(
                    category="NHI_VIOLATION",
                    scanner=self.name,
                    severity=sev,
                    evidence=f"unknown auth_type={auth_type} attempting privileged action",
                    metadata={"auth_type": auth_type},
                )
            )

        return ScannerResult(findings=findings, score=max_sev)

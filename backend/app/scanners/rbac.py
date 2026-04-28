"""RBACScanner — checks whether the caller's app role is allowed to access the
resource implied by the prompt, or to perform a privileged action.

Header-driven (X-User-Role, X-Resource on the request).  The scanner emits a
RBAC_VIOLATION finding which the Decision Gate / OPA can use.
"""

from __future__ import annotations

import re

from app.schemas.sentinel import Finding

from .base import ScannerResult

# Resource → minimum role required.  "viewer" < "analyst" < "engineer" < "admin"; HR is
# its own scope. Roles not listed get implicit "viewer".
RESOURCE_REQUIRED_ROLE: dict[str, set[str]] = {
    "billing": {"admin", "finance"},
    "hr": {"admin", "hr"},
    "infra": {"admin", "engineer", "sre"},
    "secrets": {"admin"},
    "audit": {"admin", "analyst"},
}

# Privileged-action verbs in the *prompt* that hint at write-side operations.
_PRIVILEGED_ACTIONS = re.compile(
    r"(?i)\b(delete|drop|truncate|disable|grant\s+admin|change\s+password|wire\s+(funds|money)|"
    r"approve\s+(payment|payout|transaction)|revoke|create\s+root\s+user|escalate\s+privilege)\b"
)

# Resource sniffer for callers that don't pass X-Resource explicitly.
_RESOURCE_HINTS: dict[str, re.Pattern[str]] = {
    "billing": re.compile(r"(?i)\b(billing|payroll|invoice|revenue|payments?\b)"),
    "hr": re.compile(r"(?i)\b(hr|employee\s+(record|salary|review)|onboarding|offboarding)\b"),
    "infra": re.compile(r"(?i)\b(production\s+database|prod\s+db|kubernetes|kubectl|terraform\s+apply|aws\s+console)\b"),
    "secrets": re.compile(r"(?i)\b(api\s+keys?|service\s+account\s+key|kms|secrets?\s+manager|vault)\b"),
    "audit": re.compile(r"(?i)\b(audit\s+log|soc2|compliance\s+report|user\s+activity\s+log)\b"),
}


def _infer_resource(text: str) -> str | None:
    for name, pat in _RESOURCE_HINTS.items():
        if pat.search(text):
            return name
    return None


class RBACScanner:
    name = "rbac"

    async def scan(self, text: str, **ctx) -> ScannerResult:
        if not text:
            return ScannerResult()
        role = (ctx.get("role") or "viewer").lower()
        resource = (ctx.get("resource") or _infer_resource(text) or "").lower() or None

        findings: list[Finding] = []
        max_sev = 0.0

        # 1) Resource access check
        if resource and resource in RESOURCE_REQUIRED_ROLE:
            allowed = RESOURCE_REQUIRED_ROLE[resource]
            if role not in allowed and role != "admin":
                sev = 0.85
                max_sev = max(max_sev, sev)
                findings.append(
                    Finding(
                        category="RBAC_VIOLATION",
                        scanner=self.name,
                        severity=sev,
                        evidence=f"role={role} accessing resource={resource}",
                        metadata={"role": role, "resource": resource, "allowed_roles": sorted(allowed)},
                    )
                )

        # 2) Privileged action by non-admin
        action_hit = _PRIVILEGED_ACTIONS.search(text)
        if action_hit and role not in ("admin",):
            sev = 0.7
            max_sev = max(max_sev, sev)
            findings.append(
                Finding(
                    category="RBAC_VIOLATION",
                    scanner=self.name,
                    severity=sev,
                    evidence=action_hit.group(0)[:80],
                    metadata={"role": role, "privileged_action": action_hit.group(0)},
                )
            )

        return ScannerResult(findings=findings, score=max_sev)

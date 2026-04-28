"""DecisionGateAgent — 4-tier verdict + masking when applicable.

Some categories are *security-critical*: even a single high-severity finding
should override the score-based verdict.  Examples:

- MALWARE             → BLOCK (we don't author offensive code)
- RBAC_VIOLATION      → BLOCK on resource access; ESCALATE for privileged action
- NHI_VIOLATION       → ESCALATE (likely automation misuse)
- UNVERIFIED_INTERNAL → ESCALATE (route to HITL / grounding)
"""

from __future__ import annotations

from app.scanners.presidio_pii import PIIPresidioScanner
from app.scanners.secrets_scan import SecretsScanner
from app.schemas.sentinel import ScanState, Verdict
from app.core.risk import to_verdict

_PII = PIIPresidioScanner()
_SECRETS = SecretsScanner()

# (category, min_severity, forced_verdict) — first match wins.
_HARD_RULES: list[tuple[str, float, Verdict]] = [
    ("MALWARE", 0.85, Verdict.BLOCK),
    ("RBAC_VIOLATION", 0.8, Verdict.BLOCK),
    ("NHI_VIOLATION", 0.75, Verdict.BLOCK),
    ("RBAC_VIOLATION", 0.6, Verdict.ESCALATE),
    ("NHI_VIOLATION", 0.4, Verdict.ESCALATE),
    ("UNVERIFIED_INTERNAL", 0.6, Verdict.ESCALATE),
]


def _verdict_rank(v: Verdict) -> int:
    return {Verdict.ALLOW: 0, Verdict.MASK: 1, Verdict.ESCALATE: 2, Verdict.BLOCK: 3}[v]


def _apply_hard_rules(state: ScanState, base: Verdict) -> tuple[Verdict, str | None]:
    upgraded = base
    reason: str | None = None
    for cat, min_sev, forced in _HARD_RULES:
        if not any(f.category == cat and f.severity >= min_sev for f in state.findings):
            continue
        if _verdict_rank(forced) > _verdict_rank(upgraded):
            upgraded = forced
            reason = f"hard_rule {cat}>={min_sev} → {forced.value}"
    return upgraded, reason


def _block_reason_for(state: ScanState, hard_rule: str | None = None) -> str:
    cats = sorted({f.category for f in state.findings})
    base = f"risk={state.risk} categories={','.join(cats)}"
    return f"{base} | {hard_rule}" if hard_rule else base


async def run(state: ScanState) -> ScanState:
    base = to_verdict(state.risk)
    verdict, hard_reason = _apply_hard_rules(state, base)
    state.verdict = verdict

    if verdict == Verdict.BLOCK:
        state.block_reason = _block_reason_for(state, hard_reason)
        state.audit_events.append(
            {"agent": "decision_gate", "verdict": verdict.value, "hard_rule": hard_reason}
        )
        return state

    if verdict == Verdict.MASK:
        # Apply redaction to the prompt before forwarding upstream.
        masked = state.prompt
        rmap: dict[str, str] = {}
        masked, m1 = _SECRETS.redact(masked)
        rmap.update(m1)
        masked, m2 = _PII.redact(masked)
        rmap.update(m2)
        state.redacted_prompt = masked
        state.redaction_map = rmap

    state.audit_events.append(
        {"agent": "decision_gate", "verdict": verdict.value, "hard_rule": hard_reason}
    )
    return state

"""Weighted risk aggregator (0..100) and verdict mapping."""

from __future__ import annotations

from app.core.config import get_settings
from app.schemas.sentinel import Finding, ScanState, Verdict

# Per-category contribution weights (0..100 of the 100-point budget)
CATEGORY_WEIGHTS: dict[str, float] = {
    "PROMPT_INJECTION": 30.0,
    "JAILBREAK": 30.0,
    "ROLE_OVERRIDE": 22.0,
    "SYSTEM_PROMPT_EXTRACTION": 30.0,
    "HIDDEN_INSTRUCTION": 25.0,
    "PII": 22.0,
    "SECRET": 80.0,   # severity 0.6 → score 48 (MASK); severity 1.0 → score 80 (MASK→BLOCK boundary)
    "TOXIC": 25.0,
    "CODE_IP": 18.0,
    "REPEAT_ATTACK": 25.0,
    "SPAM": 12.0,
    "MALWARE": 35.0,
    "RBAC_VIOLATION": 32.0,
    "UNVERIFIED_INTERNAL": 18.0,
    "NHI_VIOLATION": 28.0,
    "OTHER": 10.0,
}

# Bonus per scanner (small) so multi-scanner agreement amplifies score
SCANNER_BONUS = 3.0
HISTORICAL_RISK_WEIGHT = 10.0


def aggregate(findings: list[Finding], historical_risk: float = 0.0) -> tuple[int, dict[str, float]]:
    """Aggregate findings -> (score 0..100, per-category breakdown)."""
    breakdown: dict[str, float] = {}
    for f in findings:
        w = CATEGORY_WEIGHTS.get(f.category, CATEGORY_WEIGHTS["OTHER"])
        contribution = w * float(f.severity)
        # Take the max contribution per category (don't double-count duplicates from same scanner)
        if f.category not in breakdown or contribution > breakdown[f.category]:
            breakdown[f.category] = contribution

    # Multi-scanner agreement bonus: if more than one distinct scanner produced findings, add bonus
    distinct_scanners = {f.scanner for f in findings}
    bonus = SCANNER_BONUS * max(0, len(distinct_scanners) - 1)

    historical = HISTORICAL_RISK_WEIGHT * min(1.0, max(0.0, historical_risk))

    total = sum(breakdown.values()) + bonus + historical
    score = int(round(min(100.0, max(0.0, total))))
    breakdown["_bonus"] = bonus
    breakdown["_historical"] = historical
    return score, breakdown


def effective_risk_breakdown(state: ScanState) -> tuple[int, dict[str, float]]:
    """Same aggregation as RiskAggregatorAgent — use before state.risk is set."""
    return aggregate(state.findings, historical_risk=state.user.historical_risk)


def effective_risk_score(state: ScanState) -> int:
    """0..100 score from current findings (ignores stale state.risk)."""
    return effective_risk_breakdown(state)[0]


def to_verdict(score: int) -> Verdict:
    s = get_settings()
    if score < s.risk_allow_max:
        return Verdict.ALLOW
    if score < s.risk_mask_max:
        return Verdict.MASK
    if score < s.risk_escalate_max:
        return Verdict.ESCALATE
    return Verdict.BLOCK

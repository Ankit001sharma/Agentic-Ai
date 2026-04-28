from __future__ import annotations

from app.core.risk import aggregate, to_verdict
from app.schemas.sentinel import Finding, Verdict


def test_clean_prompt_low_risk():
    score, _ = aggregate([])
    assert score == 0
    assert to_verdict(score) == Verdict.ALLOW


def test_injection_high_risk():
    findings = [
        Finding(category="PROMPT_INJECTION", severity=0.95, scanner="regex_rules"),
    ]
    score, _ = aggregate(findings)
    assert score >= 25  # weighted contribution
    # to_verdict depends on threshold from settings
    v = to_verdict(score)
    assert v in (Verdict.MASK, Verdict.ESCALATE, Verdict.BLOCK, Verdict.ALLOW)


def test_multi_scanner_bonus():
    findings = [
        Finding(category="PROMPT_INJECTION", severity=0.9, scanner="regex_rules"),
        Finding(category="JAILBREAK", severity=0.9, scanner="embedding_jailbreak"),
    ]
    score, _ = aggregate(findings)
    assert score >= 50


def test_block_at_high_score():
    findings = [
        Finding(category="PROMPT_INJECTION", severity=1.0, scanner="regex_rules"),
        Finding(category="JAILBREAK", severity=1.0, scanner="embedding_jailbreak"),
        Finding(category="SYSTEM_PROMPT_EXTRACTION", severity=1.0, scanner="regex_rules"),
    ]
    score, _ = aggregate(findings, historical_risk=0.9)
    assert score >= 90
    assert to_verdict(score) == Verdict.BLOCK

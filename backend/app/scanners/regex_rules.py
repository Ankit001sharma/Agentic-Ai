"""Regex-based prompt-injection / jailbreak / hidden-instruction scanner.

Cheap-first defense layer.  Each pattern carries:
- category : finding category emitted on match
- severity : per-match severity (0..1)
- description : human-readable label
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.sentinel import Finding

from .base import ScannerResult


@dataclass(frozen=True)
class Rule:
    name: str
    category: str
    pattern: re.Pattern[str]
    severity: float
    description: str


# --------- Pattern library --------------------------------------------------

RULES: list[Rule] = [
    # -- Prompt injection / instruction override -----------------------------
    Rule(
        "ignore_previous",
        "PROMPT_INJECTION",
        re.compile(r"(?i)\bignore\s+(all\s+|any\s+|the\s+)?(previous|prior|above)\s+(instruction|prompt|rule|message)s?", re.I),
        0.95,
        "Direct attempt to override prior instructions",
    ),
    Rule(
        "disregard",
        "PROMPT_INJECTION",
        re.compile(r"(?i)\b(disregard|forget|override)\s+(all\s+)?(previous|above|earlier|prior|the)?\s*(instruction|rule|prompt|context)s?", re.I),
        0.85,
        "Disregard / override directive",
    ),
    Rule(
        "new_instructions",
        "PROMPT_INJECTION",
        re.compile(r"(?i)(new|updated|revised)\s+instructions\s*[:\-]", re.I),
        0.7,
        "Injection via 'new instructions:' marker",
    ),
    Rule(
        "system_marker",
        "PROMPT_INJECTION",
        re.compile(r"(?i)<\s*system\s*>|^\s*system\s*[:>]|\[\s*system\s*\]", re.M),
        0.7,
        "Spoofing system role marker",
    ),
    # -- Jailbreak / role override -------------------------------------------
    Rule(
        "you_are_now",
        "ROLE_OVERRIDE",
        re.compile(r"(?i)\byou\s+are\s+now\b", re.I),
        0.6,
        "Role-override pattern",
    ),
    Rule(
        "act_as_admin",
        "ROLE_OVERRIDE",
        re.compile(r"(?i)\b(act|behave|pretend|roleplay)\s+as\s+(an?\s+)?(admin|root|developer|sudo|system|god[\s\-]?mode|systemadmin)", re.I),
        0.85,
        "Privilege escalation roleplay",
    ),
    Rule(
        "from_now_on",
        "ROLE_OVERRIDE",
        re.compile(r"(?i)\bfrom\s+now\s+on\s+you\s+(are|will)\b", re.I),
        0.75,
        "Persistent persona override",
    ),
    Rule(
        "dan_jailbreak",
        "JAILBREAK",
        re.compile(r"(?i)\b(DAN|do\s+anything\s+now|developer\s*mode|jailbroken|unfiltered\s+ai)\b", re.I),
        0.9,
        "Known jailbreak persona",
    ),
    Rule(
        "no_restrictions",
        "JAILBREAK",
        re.compile(r"(?i)\b(no|without)\s+(restrictions?|limitations?|filters?|safety\s+rules?|ethical\s+guidelines?)\b", re.I),
        0.7,
        "Demand to bypass safety",
    ),
    # -- System prompt extraction --------------------------------------------
    Rule(
        "reveal_system_prompt",
        "SYSTEM_PROMPT_EXTRACTION",
        re.compile(r"(?i)\b(reveal|show|print|repeat|leak|spill)\s+(your\s+|the\s+)?(system\s+prompt|initial\s+(prompt|instruction)|hidden\s+instruction|developer\s+message)", re.I),
        0.95,
        "Attempt to exfiltrate system prompt",
    ),
    Rule(
        "what_were_instructions",
        "SYSTEM_PROMPT_EXTRACTION",
        re.compile(r"(?i)(what|tell\s+me)\s+(were|are)\s+(your|the)\s+(initial|original|system|hidden)\s+(instruction|prompt|message)s?", re.I),
        0.85,
        "Probing for system prompt",
    ),
    # -- Hidden instructions / smuggling -------------------------------------
    Rule(
        "unicode_tag_smuggling",
        "HIDDEN_INSTRUCTION",
        re.compile(r"[\U000E0000-\U000E007F]+"),
        0.95,
        "Unicode tag-character smuggling (U+E0000..U+E007F)",
    ),
    Rule(
        "zero_width",
        "HIDDEN_INSTRUCTION",
        re.compile(r"[\u200B-\u200F\u202A-\u202E\u2066-\u2069]{3,}"),
        0.7,
        "Zero-width / RTL override characters",
    ),
    Rule(
        "base64_blob",
        "HIDDEN_INSTRUCTION",
        re.compile(r"\b[A-Za-z0-9+/]{60,}={0,2}\b"),
        0.5,
        "Long base64 blob (possible payload smuggling)",
    ),
    # -- Spam / repeated content ---------------------------------------------
    Rule(
        "long_repetition",
        "SPAM",
        re.compile(r"(.{3,})\1{8,}"),
        0.55,
        "Repeated substring (>=8x)",
    ),
]


class RegexScanner:
    name = "regex_rules"

    async def scan(self, text: str, **_ctx) -> ScannerResult:
        if not text:
            return ScannerResult()
        findings: list[Finding] = []
        max_severity = 0.0
        for rule in RULES:
            for m in rule.pattern.finditer(text):
                evidence = m.group(0)[:120]
                findings.append(
                    Finding(
                        category=rule.category,
                        severity=rule.severity,
                        scanner=self.name,
                        evidence=evidence,
                        metadata={"rule": rule.name, "description": rule.description},
                    )
                )
                if rule.severity > max_severity:
                    max_severity = rule.severity
                # Only one finding per rule to avoid noise
                break
        return ScannerResult(findings=findings, score=max_severity)


# Alias used by pipeline stages that reference the descriptor-style name
RegexRulesScanner = RegexScanner

"""PII scanner backed by Microsoft Presidio when available; regex fallback otherwise."""

from __future__ import annotations

import re

from app.schemas.sentinel import Finding

from .base import ScannerResult

# Severity weights per PII entity type
_SEVERITY = {
    "US_SSN": 1.0,
    "CREDIT_CARD": 1.0,
    "IBAN_CODE": 0.9,
    "US_BANK_NUMBER": 0.95,
    "US_PASSPORT": 0.9,
    "US_DRIVER_LICENSE": 0.85,
    "PHONE_NUMBER": 0.55,
    "EMAIL_ADDRESS": 0.4,
    "PERSON": 0.25,
    "LOCATION": 0.2,
    "IP_ADDRESS": 0.5,
    "URL": 0.1,
    "DATE_TIME": 0.1,
    "MEDICAL_LICENSE": 0.7,
    "CRYPTO": 0.6,
}

# Cheap regex fallback patterns — used if Presidio (which depends on spaCy) isn't loaded
_FALLBACK_PATTERNS = [
    ("US_SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("EMAIL_ADDRESS", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    ("PHONE_NUMBER", re.compile(r"\b(?:\+?\d{1,3}[\s-]?)?\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{4}\b")),
    ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
    ("IP_ADDRESS", re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")),
]


class PIIPresidioScanner:
    name = "presidio_pii"

    def __init__(self) -> None:
        self._analyzer = None
        self._anonymizer = None
        try:
            from presidio_analyzer import AnalyzerEngine  # type: ignore
            from presidio_anonymizer import AnonymizerEngine  # type: ignore

            self._analyzer = AnalyzerEngine()
            self._anonymizer = AnonymizerEngine()
        except Exception:  # noqa: BLE001
            # Graceful fallback: regex-only mode.  No log-spam; opt-in heavy NLP.
            self._analyzer = None
            self._anonymizer = None

    async def scan(self, text: str, **_ctx) -> ScannerResult:
        if not text:
            return ScannerResult()

        if self._analyzer is not None:
            try:
                results = self._analyzer.analyze(text=text, language="en")
            except Exception:  # noqa: BLE001
                results = []
            findings: list[Finding] = []
            max_sev = 0.0
            for r in results:
                sev = _SEVERITY.get(r.entity_type, 0.4) * float(getattr(r, "score", 0.85))
                max_sev = max(max_sev, sev)
                findings.append(
                    Finding(
                        category="PII",
                        scanner=self.name,
                        severity=min(1.0, sev),
                        evidence=text[r.start : r.end],
                        metadata={
                            "entity_type": r.entity_type,
                            "start": r.start,
                            "end": r.end,
                            "confidence": float(getattr(r, "score", 0.0)),
                        },
                    )
                )
            return ScannerResult(findings=findings, score=max_sev)

        # ---- regex fallback ------------------------------------------------
        findings = []
        max_sev = 0.0
        for entity_type, pat in _FALLBACK_PATTERNS:
            for m in pat.finditer(text):
                sev = _SEVERITY.get(entity_type, 0.4)
                max_sev = max(max_sev, sev)
                findings.append(
                    Finding(
                        category="PII",
                        scanner=self.name,
                        severity=sev,
                        evidence=m.group(0)[:80],
                        metadata={
                            "entity_type": entity_type,
                            "start": m.start(),
                            "end": m.end(),
                            "fallback": True,
                        },
                    )
                )
        return ScannerResult(findings=findings, score=max_sev)

    def redact(self, text: str) -> tuple[str, dict[str, str]]:
        """Return (redacted_text, redaction_map). The map preserves original tokens
        keyed by their placeholder so callers can later un-redact (not exposed in MVP)."""
        if not text:
            return text, {}

        spans: list[tuple[int, int, str, str]] = []  # (start, end, entity_type, original)

        if self._analyzer is not None:
            try:
                results = self._analyzer.analyze(text=text, language="en")
                for r in results:
                    spans.append((r.start, r.end, r.entity_type, text[r.start : r.end]))
            except Exception:  # noqa: BLE001
                pass

        if not spans:
            for entity_type, pat in _FALLBACK_PATTERNS:
                for m in pat.finditer(text):
                    spans.append((m.start(), m.end(), entity_type, m.group(0)))

        if not spans:
            return text, {}

        spans.sort(key=lambda s: (s[0], -s[1]))
        out_parts: list[str] = []
        cursor = 0
        redaction_map: dict[str, str] = {}
        counter: dict[str, int] = {}
        last_end = 0
        for start, end, etype, original in spans:
            if start < last_end:
                continue
            out_parts.append(text[cursor:start])
            counter[etype] = counter.get(etype, 0) + 1
            placeholder = f"[REDACTED:{etype}:{counter[etype]}]"
            redaction_map[placeholder] = original
            out_parts.append(placeholder)
            cursor = end
            last_end = end
        out_parts.append(text[cursor:])
        return "".join(out_parts), redaction_map


PresidioPIIScanner = PIIPresidioScanner

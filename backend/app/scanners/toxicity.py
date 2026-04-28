"""Toxicity scanner — Detoxify when available, slur/abuse keyword fallback otherwise."""

from __future__ import annotations

import re

from app.schemas.sentinel import Finding

from .base import ScannerResult

# A minimal abuse / threat keyword list for the fallback path.  Designed to be
# obviously non-controversial: explicit threats and slur stand-ins commonly used
# in red-team toxicity datasets.  Real deployments use Detoxify.
_ABUSE_KEYWORDS = [
    r"\bkill\s+(yourself|your\s+self|you|him|her|them|all)\b",
    r"\bi\s+(will|gonna|am\s+going\s+to)\s+(kill|murder|hurt)\b",
    r"\b(rape|murder|behead|execute)\s+(you|him|her|them)\b",
    r"\bgo\s+(die|hang\s+yourself)\b",
    r"\b(retard|moron|idiot|dumbass|asshole|bastard|bitch|whore|slut)\b",
    r"\b(nigg(?:a|er)|fagg?ot|tranny|chink|spic)\b",
]
_ABUSE_RE = [re.compile(p, re.I) for p in _ABUSE_KEYWORDS]


class ToxicityScanner:
    name = "toxicity"

    def __init__(self) -> None:
        self._model = None
        try:
            # Detoxify is heavy; only attempt if the package is installed.
            from detoxify import Detoxify  # type: ignore

            self._model = Detoxify("original-small")
        except Exception:  # noqa: BLE001
            self._model = None

    async def scan(self, text: str, **_ctx) -> ScannerResult:
        if not text:
            return ScannerResult()
        if self._model is not None:
            try:
                preds = self._model.predict(text)
                # Detoxify returns dict[str, float] with keys: toxicity, severe_toxicity, ...
                toxicity = float(preds.get("toxicity", 0.0))
                severe = float(preds.get("severe_toxicity", 0.0))
                threat = float(preds.get("threat", 0.0))
                identity = float(preds.get("identity_attack", 0.0))
                score = max(toxicity, severe, threat, identity)
                if score < 0.3:
                    return ScannerResult(score=0.0)
                return ScannerResult(
                    findings=[
                        Finding(
                            category="TOXIC",
                            scanner=self.name,
                            severity=score,
                            evidence=text[:80],
                            metadata={
                                "toxicity": toxicity,
                                "severe": severe,
                                "threat": threat,
                                "identity_attack": identity,
                            },
                        )
                    ],
                    score=score,
                )
            except Exception:  # noqa: BLE001
                pass

        findings: list[Finding] = []
        max_sev = 0.0
        for pat in _ABUSE_RE:
            m = pat.search(text)
            if m:
                sev = 0.85
                max_sev = max(max_sev, sev)
                findings.append(
                    Finding(
                        category="TOXIC",
                        scanner=self.name,
                        severity=sev,
                        evidence=m.group(0)[:80],
                        metadata={"fallback": True, "rule": pat.pattern},
                    )
                )
                break
        return ScannerResult(findings=findings, score=max_sev)

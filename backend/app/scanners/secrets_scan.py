"""Secret scanner — detect-secrets when available, regex fallback otherwise."""

from __future__ import annotations

import re

from app.schemas.sentinel import Finding

from .base import ScannerResult

# Hand-crafted high-precision regex pack (used when detect-secrets is unavailable
# AND as a high-recall second pass on the response body where detect-secrets needs files).
_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    ("OpenAIKey", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}\b"), 1.0),
    ("AnthropicKey", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b"), 1.0),
    ("AWSAccessKey", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), 1.0),
    ("AWSSecretKey", re.compile(r"\b[A-Za-z0-9/+=]{40}\b(?=.*aws)", re.I), 0.7),
    ("GitHubPAT", re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"), 1.0),
    ("GitHubFineGrained", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,}\b"), 1.0),
    ("SlackBot", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), 1.0),
    ("StripeKey", re.compile(r"\b(sk|rk)_(test|live)_[A-Za-z0-9]{20,}\b"), 1.0),
    ("GoogleApiKey", re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}\b"), 0.95),
    ("PrivateKeyBlock", re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH |)PRIVATE KEY-----"), 1.0),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"), 0.7),
    ("GenericApiKey", re.compile(r"(?i)\b(api[_\-]?key|secret|token|passwd|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}", re.I), 0.6),
]


class SecretsScanner:
    name = "secrets_scan"

    def __init__(self) -> None:
        self._collection_cls = None
        try:
            from detect_secrets.core import scan as ds_scan  # type: ignore  # noqa: F401
            from detect_secrets.settings import default_settings  # type: ignore  # noqa: F401

            self._enabled = True
        except Exception:  # noqa: BLE001
            self._enabled = False

    async def scan(self, text: str, **_ctx) -> ScannerResult:
        if not text:
            return ScannerResult()

        findings: list[Finding] = []
        max_sev = 0.0

        # 1) High-precision regex pass — fast & always on
        seen_spans: set[tuple[int, int]] = set()
        for label, pat, sev in _PATTERNS:
            for m in pat.finditer(text):
                span = (m.start(), m.end())
                if span in seen_spans:
                    continue
                seen_spans.add(span)
                ev = m.group(0)
                masked = ev[:4] + "*" * max(0, len(ev) - 8) + ev[-4:] if len(ev) > 8 else "***"
                max_sev = max(max_sev, sev)
                findings.append(
                    Finding(
                        category="SECRET",
                        scanner=self.name,
                        severity=sev,
                        evidence=masked,
                        metadata={"type": label, "start": span[0], "end": span[1]},
                    )
                )

        # 2) detect-secrets pass (file-oriented, but we feed via temp memory file)
        if self._enabled:
            try:
                import tempfile

                from detect_secrets.core import scan as ds_scan  # type: ignore
                from detect_secrets.settings import default_settings  # type: ignore

                with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
                    fh.write(text)
                    fname = fh.name
                with default_settings():
                    for secret in ds_scan.scan_file(fname):
                        sev = 0.85
                        max_sev = max(max_sev, sev)
                        findings.append(
                            Finding(
                                category="SECRET",
                                scanner=self.name,
                                severity=sev,
                                evidence="(detect-secrets match)",
                                metadata={
                                    "type": secret.type,
                                    "line": secret.line_number,
                                    "ds": True,
                                },
                            )
                        )
            except Exception:  # noqa: BLE001
                pass

        return ScannerResult(findings=findings, score=max_sev)

    def redact(self, text: str) -> tuple[str, dict[str, str]]:
        spans: list[tuple[int, int, str, str]] = []
        for label, pat, _sev in _PATTERNS:
            for m in pat.finditer(text):
                spans.append((m.start(), m.end(), label, m.group(0)))
        if not spans:
            return text, {}
        spans.sort(key=lambda s: (s[0], -s[1]))
        out_parts: list[str] = []
        cursor = 0
        last_end = 0
        rm: dict[str, str] = {}
        counter: dict[str, int] = {}
        for start, end, label, original in spans:
            if start < last_end:
                continue
            out_parts.append(text[cursor:start])
            counter[label] = counter.get(label, 0) + 1
            placeholder = f"[REDACTED:SECRET:{label}:{counter[label]}]"
            rm[placeholder] = original
            out_parts.append(placeholder)
            cursor = end
            last_end = end
        out_parts.append(text[cursor:])
        return "".join(out_parts), rm

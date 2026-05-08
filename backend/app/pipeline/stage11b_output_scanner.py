"""Stage 11b — Output Scanner & Masker.

Scans tool execution results (state.tool_result) for PII, secrets, and
prompt-injection patterns *before* the result reaches Reporting, the DB,
or the HTTP response.

Sets:
    state.output_findings  — list[Finding] from the three output scanners
    state.output_risk      — 0-100 integer, max severity × 100
    state.output_verdict   — OutputVerdict.CLEAN | REDACT | BLOCK

If output_verdict is REDACT, sensitive strings inside state.tool_result["data"]
are replaced with [REDACTED:…] placeholders and the redaction map is merged
into state.redaction_map.

If output_verdict is BLOCK, the entire data payload is replaced with a blocked
message — the raw tool result is not surfaced to the caller.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.core.logging import get_logger
from app.pipeline.base import Stage
from app.scanners.presidio_pii import PIIPresidioScanner
from app.scanners.regex_rules import RegexScanner
from app.scanners.secrets_scan import SecretsScanner
from app.schemas.sentinel import Finding, OutputVerdict, ScanState

log = get_logger("pipeline.stage11b")

# Minimum finding severity to trigger redaction (PII, medium secrets)
_REDACT_THRESHOLD = 0.4
# Minimum severity at which secrets trigger a hard block
_BLOCK_THRESHOLD = 0.80


class OutputScannerStage(Stage):
    """Scans and optionally redacts tool output before it reaches reporting."""

    def __init__(self) -> None:
        self._pii = PIIPresidioScanner()
        self._secrets = SecretsScanner()
        self._regex = RegexScanner()

    async def run(self, state: ScanState) -> ScanState:
        # Only scan when a tool actually executed and produced a result
        if not state.tool_executed or state.tool_result is None:
            return state

        text = _flatten_result(state.tool_result)
        if not text.strip():
            return state

        pii_res, sec_res, regex_res = await asyncio.gather(
            self._pii.scan(text),
            self._secrets.scan(text),
            self._regex.scan(text),
            return_exceptions=True,
        )

        all_findings: list[Finding] = []
        for res in (pii_res, sec_res, regex_res):
            if isinstance(res, BaseException):
                log.warning("stage11b_scanner_error", error=str(res))
                continue
            all_findings.extend(res.findings)

        state.output_findings = all_findings

        max_sev = max((f.severity for f in all_findings), default=0.0)
        state.output_risk = int(max_sev * 100)

        # Classify verdict
        has_blocking_secret = any(
            f.category == "SECRET" and f.severity >= _BLOCK_THRESHOLD
            for f in all_findings
        )
        has_redact_trigger = any(f.severity >= _REDACT_THRESHOLD for f in all_findings)

        if has_blocking_secret:
            state.output_verdict = OutputVerdict.BLOCK
        elif has_redact_trigger:
            state.output_verdict = OutputVerdict.REDACT
        else:
            state.output_verdict = OutputVerdict.CLEAN

        # Apply masking
        if state.output_verdict == OutputVerdict.BLOCK:
            _apply_block(state)
        elif state.output_verdict == OutputVerdict.REDACT:
            _apply_redaction(state, self._pii, self._secrets)

        log.info(
            "stage11b_done",
            request_id=state.request_id,
            output_verdict=state.output_verdict.value,
            output_risk=state.output_risk,
            findings=len(all_findings),
        )
        return state


# ── Helpers ───────────────────────────────────────────────────────────────────

def _flatten_result(tool_result: dict[str, Any]) -> str:
    """Serialize tool result data to a single string for scanning."""
    try:
        target = tool_result.get("data") or tool_result
        return json.dumps(target, ensure_ascii=False)
    except Exception:
        return str(tool_result)


def _apply_block(state: ScanState) -> None:
    """Replace tool result data with a blocked sentinel payload."""
    if state.tool_result is not None:
        state.tool_result = {
            **state.tool_result,
            "data": {
                "blocked": True,
                "reason": "Output blocked: high-severity secret detected in tool result.",
            },
        }
    state.block_reason = (
        state.block_reason
        or "Tool output contained a high-severity secret and was blocked."
    )


def _apply_redaction(
    state: ScanState,
    pii: PIIPresidioScanner,
    secrets: SecretsScanner,
) -> None:
    """Recursively redact PII and secrets from tool result data."""
    if state.tool_result is None:
        return

    original_data = state.tool_result.get("data") or {}
    redacted_data, rm = _redact_value(original_data, pii, secrets)

    state.tool_result = {**state.tool_result, "data": redacted_data}
    # Merge into state.redaction_map so callers can see what was masked
    state.redaction_map = {**state.redaction_map, **rm}


def _redact_value(
    value: Any,
    pii: PIIPresidioScanner,
    secrets: SecretsScanner,
) -> tuple[Any, dict[str, str]]:
    """Recursively walk dicts/lists and redact string leaves."""
    rm: dict[str, str] = {}

    if isinstance(value, str):
        text, rm1 = pii.redact(value)
        text, rm2 = secrets.redact(text)
        rm.update(rm1)
        rm.update(rm2)
        return text, rm

    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for k, v in value.items():
            redacted_v, sub_rm = _redact_value(v, pii, secrets)
            result[k] = redacted_v
            rm.update(sub_rm)
        return result, rm

    if isinstance(value, list):
        result_list: list[Any] = []
        for item in value:
            redacted_item, sub_rm = _redact_value(item, pii, secrets)
            result_list.append(redacted_item)
            rm.update(sub_rm)
        return result_list, rm

    # Numbers, booleans, None — return as-is
    return value, rm

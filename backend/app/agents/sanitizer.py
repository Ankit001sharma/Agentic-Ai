"""ResponseSanitizerAgent — fans out 5 output scanners in parallel."""

from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.scanners.citation_validator import CitationValidator
from app.scanners.dangerous_code import DangerousCodeScanner
from app.scanners.policy_violation import PolicyViolationScanner
from app.scanners.presidio_pii import PIIPresidioScanner
from app.scanners.secrets_scan import SecretsScanner
from app.scanners.toxicity import ToxicityScanner
from app.schemas.sentinel import ScanState

log = get_logger("agent.sanitizer")

_SECRETS = SecretsScanner()
_PII = PIIPresidioScanner()
_TOX = ToxicityScanner()
_DANG = DangerousCodeScanner()
_POL = PolicyViolationScanner()
_CITE = CitationValidator()


async def run(state: ScanState) -> ScanState:
    text = state.llm_response or ""
    if not text:
        return state

    # O1 Secret Leak, O2 PII Output, O3 Toxicity/Bias, O4 Hallucination/Citation+Dangerous, O5 Policy
    results = await asyncio.gather(
        _SECRETS.scan(text),
        _PII.scan(text),
        _TOX.scan(text),
        _DANG.scan(text),
        _CITE.scan(text),
        _POL.scan(text),
        return_exceptions=True,
    )
    for r in results:
        if isinstance(r, Exception):
            log.warning("output_scanner_error", error=str(r))
            continue
        state.output_findings.extend(r.findings)

    state.audit_events.append({"agent": "sanitizer", "output_findings": len(state.output_findings)})
    return state

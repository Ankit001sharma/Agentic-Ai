"""OutputDecisionAgent — Clean / Redact / Block the LLM response."""

from __future__ import annotations

from app.core.risk import aggregate
from app.scanners.presidio_pii import PIIPresidioScanner
from app.scanners.secrets_scan import SecretsScanner
from app.schemas.sentinel import OutputVerdict, ScanState, Verdict

_PII = PIIPresidioScanner()
_SECRETS = SecretsScanner()

_SAFE_REFUSAL = (
    "I can't share that response — it was flagged by our safety policy "
    "(possible sensitive content, policy violation, or unsafe instructions)."
)


async def run(state: ScanState) -> ScanState:
    score, breakdown = aggregate(state.output_findings)
    state.output_risk = score

    # Categorical short-circuit: any DANGEROUS_CODE finding => BLOCK regardless of score
    has_dangerous = any(f.category == "DANGEROUS_CODE" for f in state.output_findings)

    if state.verdict == Verdict.BLOCK or has_dangerous or score >= 80:
        state.output_verdict = OutputVerdict.BLOCK
        state.final_response = _SAFE_REFUSAL
    elif score >= 30 or any(f.category in ("PII", "SECRET") for f in state.output_findings):
        state.output_verdict = OutputVerdict.REDACT
        text = state.llm_response or ""
        text, _ = _SECRETS.redact(text)
        text, _ = _PII.redact(text)
        state.final_response = text
    else:
        state.output_verdict = OutputVerdict.CLEAN
        state.final_response = state.llm_response

    state.audit_events.append(
        {
            "agent": "output_decision",
            "output_verdict": state.output_verdict.value,
            "output_risk": score,
            "breakdown": breakdown,
        }
    )
    return state

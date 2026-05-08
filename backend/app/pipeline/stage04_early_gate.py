"""Stage 4 — Early Gate.

Maps the risk score to BLOCK / MASK / ALLOW.
ESCALATE is not issued at this stage (that requires intent + tool context).
A BLOCK here short-circuits the entire pipeline.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import get_logger
from app.pipeline.base import Stage
from app.schemas.sentinel import ScanState, Verdict

log = get_logger("pipeline.stage04")


class EarlyGateStage(Stage):
    async def run(self, state: ScanState) -> ScanState:
        state.pipeline_stage = 4
        s = get_settings()

        score = state.risk

        if score >= s.risk_escalate_max:
            state.verdict = Verdict.BLOCK
            state.block_reason = (
                f"Risk score {score} exceeds BLOCK threshold {s.risk_escalate_max}. "
                f"Findings: {[f.category for f in state.findings[:5]]}"
            )
            log.warning(
                "stage04_block",
                request_id=state.request_id,
                risk=score,
                reason=state.block_reason,
            )
        elif score >= s.risk_mask_max:
            state.verdict = Verdict.MASK
            log.info("stage04_mask", request_id=state.request_id, risk=score)
        elif score >= s.risk_allow_max:
            state.verdict = Verdict.MASK
            log.info("stage04_mask_mid", request_id=state.request_id, risk=score)
        else:
            state.verdict = Verdict.ALLOW
            log.info("stage04_allow", request_id=state.request_id, risk=score)

        # Hard overrides: any detected secret or high-severity PII must never be ALLOW,
        # regardless of overall risk score (protects against low-weight edge cases).
        if state.verdict == Verdict.ALLOW:
            secret_findings = [f for f in state.findings if f.category == "SECRET"]
            pii_findings = [f for f in state.findings if f.category == "PII"]
            if secret_findings:
                max_secret_sev = max(f.severity for f in secret_findings)
                if max_secret_sev >= 0.85:
                    state.verdict = Verdict.BLOCK
                    state.block_reason = "High-severity secret detected in input (hard block)."
                    log.warning(
                        "stage04_secret_hard_block",
                        request_id=state.request_id,
                        max_sev=max_secret_sev,
                    )
                else:
                    state.verdict = Verdict.MASK
                    log.info(
                        "stage04_secret_hard_mask",
                        request_id=state.request_id,
                        max_sev=max_secret_sev,
                    )
            elif pii_findings:
                max_pii_sev = max(f.severity for f in pii_findings)
                if max_pii_sev >= 0.7:
                    state.verdict = Verdict.MASK
                    log.info(
                        "stage04_pii_hard_mask",
                        request_id=state.request_id,
                        max_sev=max_pii_sev,
                    )

        return state

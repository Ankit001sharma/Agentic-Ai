"""Stage 7 — OPA Policy Check.

Asks OPA: "is this user allowed to call this tool?"
On DENY the verdict is set to BLOCK and the pipeline short-circuits.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.core.policies import OPAClient
from app.pipeline.base import Stage
from app.schemas.sentinel import ScanState, Verdict

log = get_logger("pipeline.stage07")


class OPAPolicyStage(Stage):
    def __init__(self, opa_client: OPAClient | None = None) -> None:
        self._opa = opa_client or OPAClient()

    async def run(self, state: ScanState) -> ScanState:
        state.pipeline_stage = 7

        # No tool → skip OPA tool check (user+model policy checked separately)
        if not state.tool_id:
            return state

        # Already blocked upstream
        if state.verdict == Verdict.BLOCK:
            return state

        user_input = {
            "user": {
                "id": state.user.user_id,
                "tier": state.user.tier,
                "region": state.user.region,
                "role": state.user.role,
                "historical_risk": state.user.historical_risk,
            },
            "tool_id": state.tool_id,
            "resource": state.user.resource,
        }

        try:
            allowed, reasons = await self._opa.check_tool(user_input, state.tool_id)
            state.opa_allowed = allowed
            state.opa_reasons = reasons

            if not allowed:
                # Diagram: OPA deny → 200 "not permitted" + reason (not a security 403)
                state.verdict = Verdict.BLOCK  # short-circuits stages 8-11
                state.policy_denied = True
                state.block_reason = f"OPA denied tool '{state.tool_id}': {'; '.join(reasons)}"
                log.warning(
                    "stage07_deny",
                    request_id=state.request_id,
                    tool_id=state.tool_id,
                    reasons=reasons,
                )
            else:
                log.info(
                    "stage07_allow",
                    request_id=state.request_id,
                    tool_id=state.tool_id,
                )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "stage07_opa_error",
                error=str(exc),
                request_id=state.request_id,
            )
            # Fail-open with a warning (configurable in production)
            state.opa_allowed = True
            state.opa_reasons = [f"OPA unavailable: {exc}"]

        return state

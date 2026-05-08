"""Pipeline runner: wires all 14 stages into a sequential execution chain.

Usage:
    runner = PipelineRunner(redis_client)
    state  = await runner.run(state)
"""

from __future__ import annotations

import time
import uuid

import redis.asyncio as aioredis

from app.core.logging import get_logger
from app.pipeline.base import Stage
from app.pipeline.stage01_context_builder import ContextBuilderStage
from app.pipeline.stage02_input_scanners import InputScannersStage
from app.pipeline.stage03_risk_aggregator import RiskAggregatorStage
from app.pipeline.stage04_early_gate import EarlyGateStage
from app.pipeline.stage05_intent_detector import IntentDetectorStage
from app.pipeline.stage06_tool_mapping import ToolMappingStage
from app.pipeline.stage07_opa_policy import OPAPolicyStage
from app.pipeline.stage08_nemotron_fn_call import NemotronFunctionCallStage
from app.pipeline.stage09_args_sanitizer import ArgsanitizerStage
from app.pipeline.stage10_high_impact_gate import HighImpactGateStage
from app.pipeline.stage11_tool_execution import ToolExecutionStage
from app.pipeline.stage11b_output_scanner import OutputScannerStage
from app.pipeline.stage12_reporting import ReportingStage
from app.pipeline.stage13_adaptive_risk import AdaptiveRiskStage
from app.pipeline.stage14_response import ResponseStage
from app.schemas.sentinel import ScanState, UserContext, Verdict

log = get_logger("pipeline.runner")


class PipelineRunner:
    """Orchestrates the 14-stage execution pipeline."""

    def __init__(self, redis_client: aioredis.Redis) -> None:
        # Stages are constructed once; all are stateless (no instance variables
        # that change between requests).
        # Order: Stage 14 (Response) is intentionally placed BEFORE Stage 12
        # (Reporting) so that `state.final_response` is populated before the
        # audit row, SSE event, and SIEM webhook serialize it. Stage 13 runs
        # last because the persisted `historical_risk` change should reflect
        # the fully-formed verdict + response.
        self._stages: list[Stage] = [
            ContextBuilderStage(redis_client),             # Stage 1
            InputScannersStage(redis_client=redis_client), # Stage 2
            RiskAggregatorStage(),                         # Stage 3
            EarlyGateStage(),                              # Stage 4
            IntentDetectorStage(redis_client),             # Stage 5
            ToolMappingStage(),                            # Stage 6
            OPAPolicyStage(),                              # Stage 7
            NemotronFunctionCallStage(),                   # Stage 8
            ArgsanitizerStage(),                           # Stage 9
            HighImpactGateStage(redis_client),             # Stage 10
            ToolExecutionStage(redis_client),              # Stage 11
            OutputScannerStage(),                          # Stage 11b — output PII/secret masking
            ResponseStage(),                               # Stage 14 — must run before reporting
            ReportingStage(redis_client),                  # Stage 12 — persists final_response
            AdaptiveRiskStage(),                           # Stage 13 — adjusts user risk score
        ]
        # Display numbers for logs (`enumerate` index → human-readable stage label)
        self._stage_labels: list[str] = [
            "01", "02", "03", "04", "05", "06", "07", "08", "09",
            "10", "11", "11b", "14", "12", "13",
        ]
        # Indices in self._stages that MUST run for audit even on error/BLOCK
        # (Response → Reporting → Adaptive). Output scanner before them is
        # internally gated on `state.tool_executed`, so skipping it on BLOCK
        # is intentional.
        self._always_run_indices: tuple[int, ...] = (12, 13, 14)

    async def run(self, state: ScanState) -> ScanState:
        """Execute all stages sequentially.

        Invariants:
          - On a BLOCK verdict, stages 5–11b are skipped but Response,
            Reporting and Adaptive Risk still execute (audit guarantee).
          - On an uncaught stage exception, we record `pipeline_error` and
            still run the audit-tail stages so the row + SSE event + final
            response are populated. Errors raised *inside* an audit-tail
            stage are logged but never propagate (best-effort persistence).
        """
        log.info(
            "pipeline_start",
            request_id=state.request_id,
            conv_id=state.conv_id,
            user_id=state.user.user_id,
            simulate=state.simulate,
            prompt_preview=(state.prompt or "")[:120],
        )
        run_started = time.perf_counter()

        for i, stage in enumerate(self._stages):
            stage_label = self._stage_labels[i]
            stage_name = type(stage).__name__
            is_audit_tail = i in self._always_run_indices

            # Short-circuit early stages on BLOCK, but always run audit tail.
            if state.verdict == Verdict.BLOCK and not is_audit_tail:
                log.info(
                    "pipeline_skip",
                    stage=stage_label,
                    name=stage_name,
                    reason="blocked",
                    request_id=state.request_id,
                )
                continue

            stage_started = time.perf_counter()
            log.debug(
                "stage_start",
                stage=stage_label,
                name=stage_name,
                request_id=state.request_id,
            )
            try:
                state = await stage.run(state)
                state.stages_executed.append(stage_label)
                log.info(
                    "stage_done",
                    stage=stage_label,
                    name=stage_name,
                    elapsed_ms=int((time.perf_counter() - stage_started) * 1000),
                    verdict=state.verdict.value,
                    intent=state.intent,
                    tool_id=state.tool_id,
                    request_id=state.request_id,
                )
            except Exception as exc:  # noqa: BLE001
                log.exception(
                    "pipeline_stage_error",
                    stage=stage_label,
                    name=stage_name,
                    error=str(exc),
                    elapsed_ms=int((time.perf_counter() - stage_started) * 1000),
                    request_id=state.request_id,
                )
                # Audit-tail errors must not abort the loop — log and continue
                # so we still attempt to persist what we have.
                if is_audit_tail:
                    continue
                # Pre-audit error: record it and let the audit-tail stages
                # still run (response, reporting, adaptive risk). Do NOT
                # break — that would skip the audit guarantee.
                state.pipeline_error = {
                    "code": f"STAGE_{stage_label}_ERROR",
                    "message": str(exc),
                    "retryable": True,
                    "user_facing": False,
                    "stage": stage_name,
                }

        log.info(
            "pipeline_end",
            request_id=state.request_id,
            verdict=state.verdict.value,
            risk=state.risk,
            intent=state.intent,
            tool_id=state.tool_id,
            tool_executed=state.tool_executed,
            # Use the count of actually-executed stages — `state.pipeline_stage`
            # alone is no longer monotonic after the audit-tail reorder.
            stages_run=len(state.stages_executed),
            stages_executed=state.stages_executed,
            elapsed_ms=int((time.perf_counter() - run_started) * 1000),
            error=(state.pipeline_error or {}).get("code"),
        )
        return state


async def run_pipeline(
    *,
    prompt: str,
    user: UserContext,
    conv_id: str,
    redis_client: aioredis.Redis,
    simulate: bool = False,
    requested_model: str = "default",
    sensitivity: str = "normal",
) -> ScanState:
    """Convenience wrapper to build a ScanState and run the full pipeline."""
    state = ScanState(
        request_id=f"req-{uuid.uuid4().hex[:12]}",
        user=user,
        prompt=prompt,
        conv_id=conv_id,
        requested_model=requested_model,
        simulate=simulate,
        sensitivity=sensitivity,
        started_at=time.time(),
    )
    runner = PipelineRunner(redis_client)
    return await runner.run(state)

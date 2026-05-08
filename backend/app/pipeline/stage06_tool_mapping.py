"""Stage 6 — Tool Mapping Registry.

Resolves the tool_id from Stage 5 to its full YAML definition and JSON Schema.
Validates that the schema is well-formed.  Sets state.tool_schema and
state.tool_definition.  If no valid tool is found the pipeline continues
without a tool (pure conversational response path).
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.pipeline.base import Stage
from app.schemas.sentinel import ScanState
from app.tools.registry import get_tool_definition

log = get_logger("pipeline.stage06")


class ToolMappingStage(Stage):
    async def run(self, state: ScanState) -> ScanState:
        state.pipeline_stage = 6

        if not state.tool_id:
            log.info(
                "stage06_no_tool",
                request_id=state.request_id,
                intent=state.intent,
            )
            return state

        definition = get_tool_definition(state.tool_id)
        if not definition:
            log.warning(
                "stage06_unknown_tool",
                request_id=state.request_id,
                tool_id=state.tool_id,
            )
            _clear_tool(state)
            return state

        schema = definition.get("json_schema")
        if not schema or not isinstance(schema, dict):
            log.warning(
                "stage06_invalid_schema",
                tool_id=state.tool_id,
            )
            _clear_tool(state)
            return state

        state.tool_definition = definition
        state.tool_schema = schema
        state.high_impact = bool(definition.get("high_impact", False))

        log.info(
            "stage06_done",
            request_id=state.request_id,
            tool_id=state.tool_id,
            high_impact=state.high_impact,
        )
        return state


def _clear_tool(state: ScanState) -> None:
    """Drop the tool resolution from BOTH the flat field and the nested
    IntentResult so consumers (build_response_payload, analytics) don't see
    contradictory tool_ids in the same record.
    """
    state.tool_id = None
    if state.intent_result is not None:
        state.intent_result.tool_id = None

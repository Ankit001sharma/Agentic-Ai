"""IntentAgent — classifies user intent."""

from __future__ import annotations

import time

from app.agents.specialists.base import append_finding, classify_intent_json
from app.agents.tools.base import ToolResult
from app.schemas.explanation import AgentFindingRecord
from app.schemas.sentinel import ScanState


async def run(state: ScanState) -> ToolResult:
    t0 = time.perf_counter()
    data = await classify_intent_json(state.prompt)
    state.intent = str(data.get("intent", "general_chat"))
    state.intent_sub = str(data.get("sub_intent", ""))
    state.intent_confidence = float(data.get("confidence", 0.5))
    append_finding(
        state,
        AgentFindingRecord(
            agent="intent",
            claim=f"Intent={state.intent}",
            evidence=[str(data.get("evidence", ""))],
            confidence=state.intent_confidence,
            metadata={"raw": data},
        ),
    )
    return ToolResult(
        ok=True,
        name="intent",
        summary=f"intent={state.intent} conf={state.intent_confidence:.2f}",
        data=data,
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )

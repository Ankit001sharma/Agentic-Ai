"""MultimodalAgent — routes attachments to image/doc/url/metadata sub-specialists."""

from __future__ import annotations

import asyncio
import time

from app.agents.specialists import mm_document, mm_image, mm_metadata, mm_url
from app.schemas.explanation import AgentFindingRecord
from app.agents.specialists.base import append_finding
from app.agents.tools.base import ToolResult
from app.schemas.sentinel import ScanState


async def run(state: ScanState) -> ToolResult:
    t0 = time.perf_counter()
    if not state.attachments:
        return ToolResult(
            ok=True,
            name="multimodal",
            summary="no attachments",
            data={},
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )

    tasks: list = [mm_url.analyze_prompt_and_attachments(state)]
    for att in state.attachments:
        tasks.append(mm_image.analyze_attachment(state, att))
        tasks.append(mm_document.analyze_attachment(state, att))
        tasks.append(mm_metadata.analyze_attachment(state, att))

    await asyncio.gather(*tasks)

    append_finding(
        state,
        AgentFindingRecord(
            agent="multimodal",
            claim="multimodal_subagents_ran",
            evidence=[f"attachments={len(state.attachments)}"],
            confidence=0.55,
            metadata={"attachments": len(state.attachments)},
        ),
    )
    return ToolResult(
        ok=True,
        name="multimodal",
        summary=f"attachments={len(state.attachments)}",
        data={"attachments": len(state.attachments)},
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )

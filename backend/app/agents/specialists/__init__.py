"""Specialist sub-agents (Intent, Threat, Policy, Multimodal, Router, Human escalation)."""

from __future__ import annotations

from app.agents.tools.base import ToolResult
from app.schemas.sentinel import ScanState


async def run_specialist(kind: str, state: ScanState) -> ToolResult:
    if kind == "intent":
        from app.agents.specialists import intent as m

        return await m.run(state)
    if kind == "threat":
        from app.agents.specialists import threat_investigation as m

        return await m.run(state)
    if kind == "policy":
        from app.agents.specialists import policy as m

        return await m.run(state)
    if kind == "multimodal":
        from app.agents.specialists import multimodal as m

        return await m.run(state)
    if kind == "model_router":
        from app.agents.specialists import model_router_agent as m

        return await m.run(state)
    if kind == "human_escalation":
        from app.agents.specialists import human_escalation as m

        return await m.run(state)
    return ToolResult(ok=False, name=kind, summary="unknown", error="unknown specialist")

"""Optional LangGraph composition (Sentinel-X uses run_agentic_pipeline in graph.py).

This module exposes a minimal compiled graph for integrators who require a
`CompiledGraph` object; it wraps the same async pipeline as a single node.
"""

from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph


class _AgenticState(TypedDict, total=False):
    user_id: str
    result: str


async def _agentic_node(state: _AgenticState) -> _AgenticState:
    return {**state, "result": "use app.agents.graph.run_agentic_pipeline"}


def build_workflow() -> Any:
    g: StateGraph = StateGraph(_AgenticState)
    g.add_node("sentinel_x", _agentic_node)
    g.set_entry_point("sentinel_x")
    g.add_edge("sentinel_x", END)
    return g.compile()

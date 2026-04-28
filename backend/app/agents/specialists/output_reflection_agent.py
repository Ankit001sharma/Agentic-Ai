"""OutputReflectionAgent specialist — wraps core output reflection + blackboard trace."""

from __future__ import annotations

from app.agents import output_reflection as core
from app.schemas.explanation import AgentFindingRecord
from app.agents.specialists.base import append_finding
from app.schemas.sentinel import ScanState


async def run(state: ScanState) -> ScanState:
    """Post-LLM review; updates rewrite_constraints and output verdict."""
    state = await core.run(state)
    append_finding(
        state,
        AgentFindingRecord(
            agent="output_reflection",
            claim=f"output_reflection_verdict={state.output_reflection_verdict}",
            evidence=(state.rewrite_constraints or [])[:8],
            confidence=0.75,
            metadata={"output_verdict": state.output_verdict.value if hasattr(state.output_verdict, "value") else str(state.output_verdict)},
        ),
    )
    return state

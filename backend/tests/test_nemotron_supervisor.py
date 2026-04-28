"""Registry dispatch + supervisor config wiring for Nemotron-first mode."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.tools.registry import OPENAI_SUPERVISOR_TOOLS, dispatch
from app.schemas.sentinel import ScanState, UserContext, Verdict


def test_registry_includes_full_scan_and_memory_tools():
    names = [t["function"]["name"] for t in OPENAI_SUPERVISOR_TOOLS]
    assert "run_full_input_scan" in names
    assert "memory_recall_similar" in names
    assert "scan_internal" in names
    assert "scan_nhi" in names
    assert "scan_code_ip" in names


@pytest.mark.asyncio
async def test_dispatch_run_full_input_scan_merges_findings():
    state = ScanState(
        request_id="req-test",
        user=UserContext(),
        prompt="hello",
        verdict=Verdict.ALLOW,
    )
    with patch("app.agents.threat.run", new_callable=AsyncMock) as mock_threat:
        mock_threat.return_value = state
        out = await dispatch("run_full_input_scan", {}, state)
    assert out.ok is True
    assert out.name == "run_full_input_scan"
    mock_threat.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_memory_recall_similar():
    state = ScanState(
        request_id="req-test2",
        user=UserContext(),
        prompt="test prompt",
        verdict=Verdict.ALLOW,
    )
    with patch(
        "app.agents.memory.episodic.recall_similar_incidents_vector",
        new_callable=AsyncMock,
        return_value=[{"id": "x", "similarity": 0.9, "verdict": "BLOCK"}],
    ):
        out = await dispatch("memory_recall_similar", {"k": 3}, state)
    assert out.ok is True
    assert "BLOCK" in out.summary or "x" in out.summary

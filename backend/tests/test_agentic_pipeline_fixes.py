"""Tests for effective risk alignment, policy probe, and supervisor traces."""

from __future__ import annotations

import pytest

from app.agents.risk_aggregator import run as risk_run
from app.agents.specialists import policy as policy_mod
from app.agents.tools.registry import dispatch, supervisor_tool_names_hint
from app.core.risk import effective_risk_score, to_verdict
from app.schemas.sentinel import Finding, ScanState, UserContext, Verdict


def _minimal_state(**kwargs) -> ScanState:
    base = dict(
        request_id="req-test",
        user=UserContext(user_id="u1", tier="free"),
        prompt="hello",
        requested_model="gpt-4o-mini",
    )
    base.update(kwargs)
    return ScanState(**base)


@pytest.mark.asyncio
async def test_effective_risk_score_matches_aggregator_with_stale_state_risk():
    f = Finding(category="PII", severity=1.0, scanner="test", evidence="x")
    state = _minimal_state(findings=[f], risk=0)
    assert effective_risk_score(state) > 0
    after = await risk_run(state)
    assert after.risk == effective_risk_score(state)


@pytest.mark.asyncio
async def test_policy_run_uses_findings_when_state_risk_zero():
    """policy base tier must follow aggregated findings, not stale state.risk."""
    f = Finding(category="PII", severity=1.0, scanner="test", evidence="x")
    state = _minimal_state(findings=[f], risk=0, verdict=Verdict.ALLOW)
    layers = await policy_mod.evaluate_policy_layers(state)
    assert layers.base_verdict == to_verdict(effective_risk_score(state))


@pytest.mark.asyncio
async def test_probe_does_not_mutate_verdict():
    state = _minimal_state(
        findings=[
            Finding(category="OTHER", severity=0.1, scanner="s", evidence=""),
        ],
        verdict=Verdict.ALLOW,
    )
    before = state.verdict
    await policy_mod.probe(state)
    assert state.verdict == before


@pytest.mark.asyncio
async def test_delegate_to_policy_dispatches_probe_not_full_policy():
    state = _minimal_state(verdict=Verdict.ALLOW)
    before = state.verdict
    out = await dispatch("delegate_to_policy", {}, state)
    assert out.name == "policy_probe"
    assert state.verdict == before


@pytest.mark.asyncio
async def test_unknown_tool_summary_lists_names():
    state = _minimal_state()
    out = await dispatch("not_a_real_tool_xyz", {}, state)
    assert not out.ok
    assert "delegate_to_intent" in (out.summary or "")
    assert "emit_explanation_card" in supervisor_tool_names_hint()


@pytest.mark.asyncio
async def test_supervisor_nemotron_skipped_without_vllm(monkeypatch):
    from types import SimpleNamespace

    from app.agents import supervisor as sup

    fake = SimpleNamespace(
        vllm_base_url="",
        agent_prescan="none",
        supervisor_max_steps=1,
        supervisor_mode="react_primary",
        memory_recall_top_k=5,
    )
    monkeypatch.setattr("app.agents.supervisor.get_settings", lambda: fake)

    state = _minimal_state()
    await sup.run(state)
    skipped = [s for s in state.agent_steps if s.get("tool") == "nemotron_skipped"]
    assert skipped and skipped[0].get("observation") == "no_vllm"

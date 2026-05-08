"""Fast intent path and operator Nemotron policy loading."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.agents.prompts import nemotron_supervisor as ns
from app.agents.specialists.base import classify_intent_json
from app.core.config import get_settings


@pytest.fixture
def clear_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_load_operator_llm_policy_truncates(monkeypatch, tmp_path, clear_settings):
    p = tmp_path / "pol.md"
    p.write_text("x" * 500, encoding="utf-8")
    monkeypatch.setenv("OPERATOR_LLM_POLICY_PATH", str(p))
    monkeypatch.setenv("OPERATOR_LLM_POLICY_MAX_CHARS", "20")
    get_settings.cache_clear()
    text = ns.load_operator_llm_policy_text()
    assert len(text) == 20


def test_build_nemotron_supervisor_system_includes_operator_block(monkeypatch, tmp_path, clear_settings):
    p = tmp_path / "custom.md"
    p.write_text("Always cite tool names.", encoding="utf-8")
    monkeypatch.setenv("OPERATOR_LLM_POLICY_PATH", str(p))
    get_settings.cache_clear()
    built = ns.build_nemotron_supervisor_system()
    assert "Sentinel-X" in built
    assert "## Operator policies" in built
    assert "Always cite tool names." in built


@pytest.mark.asyncio
async def test_classify_intent_json_prefers_fast_path(clear_settings):
    async def fake_fast(messages):
        return '{"intent":"general_chat","sub_intent":"x","confidence":0.9,"evidence":"ok"}', "openai/m", False

    with patch("app.agents.specialists.base.acomplete_intent_fast", new=fake_fast):
        with patch("app.agents.specialists.base.acomplete", new_callable=AsyncMock) as mock_ac:
            out = await classify_intent_json("hello world")
    assert out["intent"] == "general_chat"
    assert out["confidence"] == 0.9
    mock_ac.assert_not_called()


@pytest.mark.asyncio
async def test_classify_intent_json_fallback_on_fast_failure(monkeypatch, clear_settings):
    monkeypatch.setenv("INTENT_FALLBACK_TO_PLANNER", "true")
    get_settings.cache_clear()

    async def boom(messages):
        raise RuntimeError("no_intent_llm_route")

    async def fake_acomplete(messages, **kwargs):
        return '{"intent":"jailbreak_attempt","sub_intent":"","confidence":0.5,"evidence":"fb"}', "openai/x", False

    with patch("app.agents.specialists.base.acomplete_intent_fast", new=boom):
        with patch("app.agents.specialists.base.acomplete", new=fake_acomplete):
            out = await classify_intent_json("test")
    assert out["intent"] == "jailbreak_attempt"

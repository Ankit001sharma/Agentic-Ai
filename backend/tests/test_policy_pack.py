"""Security Software LLM Guard policy_pack YAML load and Nemotron injection."""

from pathlib import Path

import pytest

from app.agents.prompts import nemotron_supervisor as ns
from app.agents.prompts.policy_pack_render import (
    load_policy_pack,
    render_policy_pack_for_prompt,
    render_policy_pack_markdown,
)


@pytest.fixture
def clear_settings():
    ns.get_settings.cache_clear()
    yield
    ns.get_settings.cache_clear()


def _bundled_yaml() -> Path:
    return Path(ns.__file__).resolve().parent / "security_software_llm_guard_policies.yaml"


def test_policy_pack_yaml_loads():
    pack = load_policy_pack(_bundled_yaml())
    assert pack.get("name") == "Security Software Company LLM Guard Policies"
    assert pack.get("version") == "2.0"
    ids = [p["id"] for p in pack.get("policies", []) if isinstance(p, dict)]
    assert "IAM-001" in ids
    assert "DATA-002" in ids


def test_render_policy_pack_markdown_contains_markers():
    pack = load_policy_pack(_bundled_yaml())
    md = render_policy_pack_markdown(pack)
    assert "Security Software Company LLM Guard Policies" in md
    assert "### IAM-001:" in md
    assert "Tenant Isolation" in md
    assert "## Execution flow" in md
    assert "## Response templates" in md


def test_render_policy_pack_for_prompt_respects_max_chars():
    text, truncated = render_policy_pack_for_prompt(_bundled_yaml(), 5000)
    assert len(text) <= 5000
    assert isinstance(truncated, bool)


def test_load_operator_llm_policy_default_includes_pack(monkeypatch, clear_settings):
    monkeypatch.delenv("OPERATOR_LLM_POLICY_PATH", raising=False)
    text = ns.load_operator_llm_policy_text()
    assert "Security Software Company LLM Guard Policies" in text
    assert "IAM-001" in text


def test_build_nemotron_supervisor_system_includes_operator_block(monkeypatch, clear_settings):
    monkeypatch.delenv("OPERATOR_LLM_POLICY_PATH", raising=False)
    built = ns.build_nemotron_supervisor_system()
    assert "Sentinel-X" in built
    assert "## Operator policies" in built
    assert "Security Software Company LLM Guard Policies" in built


def test_operator_policy_yaml_override_path(tmp_path, monkeypatch, clear_settings):
    src = _bundled_yaml()
    dst = tmp_path / "custom_pack.yaml"
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("OPERATOR_LLM_POLICY_PATH", str(dst))
    text = ns.load_operator_llm_policy_text()
    assert "IAM-001" in text

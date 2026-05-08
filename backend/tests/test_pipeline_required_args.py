from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.pipeline.stage08_nemotron_fn_call import _populate_state
from app.pipeline.stage11_tool_execution import ToolExecutionStage, _normalize_fallback_args
from app.schemas.sentinel import FunctionCallResult, ScanState, UserContext


def _make_state(prompt: str = "i want to know about SAML plugin from miniOrange") -> ScanState:
    return ScanState(
        request_id="req-test-required-args",
        user=UserContext(user_id="u1", role="viewer", tier="free"),
        prompt=prompt,
        tool_id="query_miniorange_docs",
        tool_schema={
            "type": "object",
            "required": ["query"],
            "properties": {"query": {"type": "string"}},
        },
    )


def test_stage08_populate_state_fills_query_from_prompt_when_missing() -> None:
    state = _make_state()
    result = FunctionCallResult(
        tool_id="query_miniorange_docs",
        arguments={},
        missing_required_fields=[],
    )

    _populate_state(state, result)

    assert state.tool_args.get("query") == state.prompt
    assert "query" not in state.missing_required_fields


@pytest.mark.asyncio
async def test_stage11_skips_execution_when_required_fields_missing() -> None:
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=None)
    redis.expire = AsyncMock(return_value=None)
    redis.lpush = AsyncMock(return_value=None)
    redis.xadd = AsyncMock(return_value=None)

    stage = ToolExecutionStage(redis)
    state = _make_state(prompt="")
    state.tool_args = {}
    state.missing_required_fields = ["query"]

    out = await stage.run(state)

    assert out.tool_executed is False
    assert out.tool_result is None
    assert out.pipeline_error is None


def test_stage11_fallback_populates_miniorange_query_from_prompt() -> None:
    args = _normalize_fallback_args("query_miniorange_docs", {}, "tell me about miniorange")
    assert args.get("query") == "tell me about miniorange"


def test_stage11_fallback_populates_github_username_from_prompt() -> None:
    args = _normalize_fallback_args("github_lookup_user", {}, "lookup the github user 'Ankit001sharma'")
    assert args.get("username") == "Ankit001sharma"

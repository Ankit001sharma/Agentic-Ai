from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.tools.github_tool import GitHubToolExecutor, _extract_username


def test_extract_username_accepts_aliases() -> None:
    assert _extract_username({"username": "ankit001"}) == "ankit001"
    assert _extract_username({"user": "@ankit001"}) == "ankit001"
    assert _extract_username({"login": "  ankit001  "}) == "ankit001"
    assert _extract_username({"handle": "ankit001"}) == "ankit001"


@pytest.mark.asyncio
async def test_lookup_user_returns_invalid_args_when_username_missing() -> None:
    tool = GitHubToolExecutor()
    client = MagicMock()
    client.get = AsyncMock()

    result = await tool._lookup_user({}, {}, client, 5.0, "ik-test")

    assert result.success is False
    assert (result.error or {}).get("code") == "TOOL_INVALID_ARGS"
    assert (result.error or {}).get("user_facing") is True
    client.get.assert_not_called()

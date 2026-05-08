"""Tool registry: loads tools.yaml and resolves tool definitions + executors."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import yaml

from app.core.config import get_settings
from app.core.logging import get_logger
from app.tools.base import ToolExecutor, ToolResult

log = get_logger("tools.registry")


def _github_tool_ids() -> set[str]:
    from app.tools.github_tool import GITHUB_TOOL_IDS
    return GITHUB_TOOL_IDS


@lru_cache(maxsize=1)
def _load_tools_yaml() -> list[dict[str, Any]]:
    s = get_settings()
    path = s.tools_yaml_path
    # Resolve relative paths from the backend working directory
    if not os.path.isabs(path):
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = os.path.join(base, path)
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("tools", [])


def get_tool_definition(tool_id: str) -> dict[str, Any] | None:
    """Return the raw YAML dict for a tool_id, or None if not found."""
    for tool in _load_tools_yaml():
        if tool.get("id") == tool_id:
            return tool
    return None


def list_tool_ids() -> list[str]:
    return [t["id"] for t in _load_tools_yaml()]


def _build_executor(tool_id: str) -> ToolExecutor | None:
    """Lazy-import and instantiate the correct executor for a tool_id."""
    # Local import to avoid circular deps and enable optional dependencies
    if tool_id == "send_email":
        from app.tools.email_tool import EmailToolExecutor
        return EmailToolExecutor()
    if tool_id in _github_tool_ids():
        from app.tools.github_tool import GitHubToolExecutor
        return GitHubToolExecutor()
    if tool_id == "send_slack_message":
        from app.tools.slack_tool import SlackToolExecutor
        return SlackToolExecutor()
    if tool_id == "search_web":
        from app.tools.search_tool import SearchToolExecutor
        return SearchToolExecutor()
    if tool_id == "search_docs":
        from app.tools.search_tool import DocsSearchExecutor
        return DocsSearchExecutor()
    if tool_id == "query_miniorange_docs":
        from app.tools.miniorange_tool import QueryMiniOrangeDocsExecutor
        return QueryMiniOrangeDocsExecutor()
    if tool_id == "list_miniorange_plugins":
        from app.tools.miniorange_tool import ListMiniOrangePluginsExecutor
        return ListMiniOrangePluginsExecutor()
    if tool_id == "get_miniorange_plugin":
        from app.tools.miniorange_tool import GetMiniOrangePluginExecutor
        return GetMiniOrangePluginExecutor()
    return None


async def execute_tool(
    tool_id: str,
    args: dict[str, Any],
    *,
    idempotency_key: str,
    simulate: bool = False,
) -> ToolResult:
    """Resolve + execute a tool by ID.  Returns ToolResult (success or failure)."""
    executor = _build_executor(tool_id)
    if executor is None:
        return ToolResult.fail(
            tool_id,
            code="TOOL_NOT_IMPLEMENTED",
            message=f"No executor registered for tool '{tool_id}'",
            retryable=False,
            user_facing=True,
            idempotency_key=idempotency_key,
        )
    try:
        # Inject _action so multi-action executors (e.g. GitHubToolExecutor) know which
        # operation to perform without needing a separate constructor per tool_id.
        effective_args = {**args, "_action": tool_id}
        return await executor.execute(
            effective_args,
            idempotency_key=idempotency_key,
            simulate=simulate,
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("tool_execution_error", tool_id=tool_id, error=str(exc))
        return ToolResult.fail(
            tool_id,
            code="TOOL_EXECUTION_ERROR",
            message=str(exc),
            retryable=True,
            user_facing=False,
            idempotency_key=idempotency_key,
        )

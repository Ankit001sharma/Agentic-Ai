"""Stage 11 — Tool Execution.

Calls the resolved tool via the registry, enforcing:
  - Idempotency key on every call
  - Hard timeout from tool definition
  - simulate=true dry-run support
  - Captures result or structured error
  - Writes tool + result to STM after successful execution
"""

from __future__ import annotations

import asyncio
import json
import re
import time

import redis.asyncio as aioredis

from app.core.logging import get_logger
from app.memory.stm import ShortTermMemory
from app.pipeline.base import Stage
from app.schemas.sentinel import ScanState, Verdict
from app.tools.registry import execute_tool

log = get_logger("pipeline.stage11")


# region agent log
def _debug_log(run_id: str, hypothesis_id: str, location: str, message: str, data: dict) -> None:
    try:
        payload = {
            "sessionId": "caa63e",
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with open("debug-caa63e.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
# endregion


class ToolExecutionStage(Stage):
    def __init__(self, redis_client: aioredis.Redis) -> None:
        self._stm = ShortTermMemory(redis_client)

    async def run(self, state: ScanState) -> ScanState:
        state.pipeline_stage = 11

        if not state.tool_id or state.verdict == Verdict.BLOCK:
            return state

        # region agent log
        _debug_log(
            state.request_id,
            "H2",
            "stage11_tool_execution.py:run:entry",
            "stage11 entry",
            {
                "tool_id": state.tool_id,
                "verdict": state.verdict.value,
                "missing_required_fields": list(state.missing_required_fields),
                "tool_args_keys": sorted(list((state.tool_args or {}).keys())),
                "code_version": "stage11-debug-v1",
            },
        )
        # endregion

        if state.missing_required_fields:
            log.info(
                "stage11_skip_missing_required_fields",
                request_id=state.request_id,
                tool_id=state.tool_id,
                missing=state.missing_required_fields,
            )
            # region agent log
            _debug_log(
                state.request_id,
                "H3",
                "stage11_tool_execution.py:run:missing_required_skip",
                "stage11 skipped due missing required fields",
                {
                    "tool_id": state.tool_id,
                    "missing_required_fields": list(state.missing_required_fields),
                },
            )
            # endregion
            return state

        timeout = float(
            (state.tool_definition or {}).get("timeout_seconds", 10)
        )
        tool_id = state.tool_id
        args = _normalize_fallback_args(tool_id, dict(state.tool_args), state.prompt)
        simulate = state.simulate
        # region agent log
        _debug_log(
            state.request_id,
            "H4",
            "stage11_tool_execution.py:run:before_execute",
            "stage11 normalized args",
            {
                "tool_id": tool_id,
                "args_keys": sorted(list(args.keys())),
                "has_query": isinstance(args.get("query"), str) and bool(args.get("query", "").strip()),
                "has_username": isinstance(args.get("username"), str) and bool(args.get("username", "").strip()),
            },
        )
        # endregion

        log.info(
            "stage11_execute",
            request_id=state.request_id,
            tool_id=tool_id,
            simulate=simulate,
            idempotency_key=state.idempotency_key,
        )

        try:
            result = await asyncio.wait_for(
                execute_tool(
                    tool_id,
                    args,
                    idempotency_key=state.idempotency_key,
                    simulate=simulate,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            err = {
                "code": "TOOL_TIMEOUT",
                "message": f"Tool '{tool_id}' timed out after {timeout}s",
                "retryable": True,
                "user_facing": True,
            }
            state.tool_result = {"success": False, "error": err}
            state.pipeline_error = err
            log.warning("stage11_timeout", request_id=state.request_id, tool_id=tool_id)
            return state
        except Exception as exc:  # noqa: BLE001
            err = {
                "code": "TOOL_EXECUTION_ERROR",
                "message": str(exc)[:400],
                "retryable": False,
                "user_facing": False,
            }
            state.tool_result = {"success": False, "error": err}
            state.pipeline_error = err
            log.exception("stage11_error", request_id=state.request_id, tool_id=tool_id, error=str(exc))
            return state

        state.tool_result = result.model_dump()
        state.tool_executed = True
        # region agent log
        _debug_log(
            state.request_id,
            "H6",
            "stage11_tool_execution.py:run:after_execute",
            "stage11 tool execution returned",
            {
                "tool_id": tool_id,
                "success": bool(result.success),
                "error_code": (result.error or {}).get("code") if result.error else None,
                "user_facing": (result.error or {}).get("user_facing") if result.error else None,
            },
        )
        # endregion

        if not result.success:
            state.pipeline_error = result.error
            log.warning(
                "stage11_tool_failed",
                request_id=state.request_id,
                tool_id=tool_id,
                error=result.error,
            )
        else:
            log.info(
                "stage11_done",
                request_id=state.request_id,
                tool_id=tool_id,
                simulated=result.simulated,
            )
            # Write to STM — args redacted inside ShortTermMemory._redact
            if state.user.user_id != "anonymous":
                await self._stm.update_tool_result(
                    state.user.user_id,
                    state.conv_id,
                    tool_id,
                    args,
                    result.data,
                )

        return state


def _normalize_fallback_args(tool_id: str, args: dict, prompt: str) -> dict:
    """Best-effort arg normalization to reduce LLM arg-shape failures."""
    prompt_text = (prompt or "").strip()
    if tool_id == "query_miniorange_docs":
        query = args.get("query")
        if not isinstance(query, str) or not query.strip():
            if prompt_text:
                args["query"] = prompt_text
    elif tool_id == "github_lookup_user":
        username = args.get("username")
        if not isinstance(username, str) or not username.strip():
            inferred = _extract_username_from_prompt(prompt_text)
            if inferred:
                args["username"] = inferred
    return args


def _extract_username_from_prompt(prompt: str) -> str:
    if not prompt:
        return ""
    # Prefer quoted usernames if provided.
    quoted = re.search(r"[\"'](@?[A-Za-z0-9-]{1,39})[\"']", prompt)
    if quoted:
        return quoted.group(1).lstrip("@")
    # Fallback to the first @handle.
    handle = re.search(r"@([A-Za-z0-9-]{1,39})", prompt)
    if handle:
        return handle.group(1)
    # Last token fallback for phrases like "lookup github user ankit001".
    tokens = re.findall(r"[A-Za-z0-9-]{1,39}", prompt)
    if tokens:
        return tokens[-1]
    return ""

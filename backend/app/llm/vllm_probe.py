"""One-shot probe at startup: can vLLM return tool_calls in the OpenAI format?"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.llm import vllm_state

log = get_logger("vllm_probe")


async def probe_vllm_tooling() -> None:
    """Sets vllm_state.vllm_tool_mode to 'native' or 'json' and vllm_healthy."""
    s = get_settings()
    mode = (s.vllm_tool_calling_mode or "auto").lower()
    if mode in ("native", "json"):
        vllm_state.vllm_tool_mode = mode
        vllm_state.vllm_healthy = bool(s.vllm_base_url)
        return

    if not s.vllm_base_url or not s.vllm_planner_model:
        vllm_state.vllm_tool_mode = "json"
        vllm_state.vllm_healthy = False
        vllm_state.vllm_probe_error = "no_vllm_base"
        return

    base = s.vllm_base_url.rstrip("/")
    if not base.endswith("/v1"):
        base = base + "/v1"
    model = s.vllm_planner_model
    # OpenAI-style chat completions with tools
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "Use the get_weather tool to check weather in Paris. Reply with tool call only.",
            }
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather for a city",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                        "required": ["city"],
                    },
                },
            }
        ],
        "tool_choice": "auto",
        "max_tokens": 100,
    }
    headers = {
        "Authorization": f"Bearer {s.vllm_api_key or 'EMPTY'}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as c:
            r = await c.post(f"{base}/chat/completions", json=body, headers=headers)
            r.raise_for_status()
            data = r.json() or {}
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        tool_calls = msg.get("tool_calls")
        if tool_calls and isinstance(tool_calls, list) and len(tool_calls) > 0:
            vllm_state.vllm_tool_mode = "native"
            vllm_state.vllm_healthy = True
            vllm_state.vllm_probe_error = None
            log.info("vllm_probe_ok", mode="native")
        else:
            vllm_state.vllm_tool_mode = "json"
            vllm_state.vllm_healthy = True
            vllm_state.vllm_probe_error = None
            log.info("vllm_probe_fallback", mode="json", reason="no_tool_calls_in_response")
    except Exception as e:  # noqa: BLE001
        vllm_state.vllm_tool_mode = "json"
        vllm_state.vllm_healthy = False
        vllm_state.vllm_probe_error = str(e)
        log.warning("vllm_probe_failed", error=str(e), mode="json")

"""One-shot probe at startup: can vLLM return tool_calls in the OpenAI format?"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.llm import vllm_state
from app.llm.vllm_url import normalize_openai_compatible_base

log = get_logger("vllm_probe")


def _api_base_from_request_url(request_url: str) -> str | None:
    """Derive .../v1 from the final URL httpx used after redirects."""
    p = urlparse(request_url)
    if not p.scheme or not p.netloc:
        return None
    return f"{p.scheme}://{p.netloc}/v1"


async def _resolve_openai_api_base(bare_base: str, headers: dict[str, str]) -> str | None:
    """Discover …/v1 using redirect-following GETs so http→https and :port match the real server.

    Tries ``/v1/models`` first (OpenAI-compatible servers), then ``/`` as a fallback when the
    models route is absent — both still capture the final scheme/host/port after redirects.
    """
    bare = bare_base.rstrip("/")
    paths = ("/v1/models", "/")
    last_err: Exception | None = None
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as c:
            for path in paths:
                try:
                    r = await c.get(f"{bare}{path}", headers=headers)
                    resolved = _api_base_from_request_url(str(r.url))
                    if resolved:
                        return resolved
                except Exception as e:  # noqa: BLE001
                    last_err = e
                    log.debug("vllm_resolve_probe_try", path=path, error=str(e))
    except Exception as e:  # noqa: BLE001
        last_err = e
        log.debug("vllm_resolve_models_probe_optional", error=str(e))
        return None
    if last_err:
        log.debug("vllm_resolve_models_probe_optional", error=str(last_err))
    return None


async def probe_vllm_tooling() -> None:
    """Sets vllm_state.vllm_tool_mode to 'native' or 'json' and vllm_healthy."""
    s = get_settings()
    vllm_state.resolved_api_base = None
    vllm_state.resolved_intent_api_base = None

    mode = (s.vllm_tool_calling_mode or "auto").lower()
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if (s.vllm_api_key or "").strip():
        headers["Authorization"] = f"Bearer {s.vllm_api_key}"

    if mode in ("native", "json"):
        vllm_state.vllm_tool_mode = mode
        if s.vllm_base_url:
            bare_locked = normalize_openai_compatible_base(s.vllm_base_url)
            vllm_state.resolved_api_base = await _resolve_openai_api_base(bare_locked, headers)
            intent_raw = (s.vllm_intent_base_url or "").strip()
            main_norm = s.vllm_base_url.strip().rstrip("/")
            if intent_raw and intent_raw.rstrip("/") != main_norm:
                vllm_state.resolved_intent_api_base = await _resolve_openai_api_base(
                    normalize_openai_compatible_base(intent_raw), headers
                )
        vllm_state.vllm_healthy = bool(s.vllm_base_url)
        return

    if not s.vllm_base_url or not s.vllm_planner_model:
        vllm_state.vllm_tool_mode = "json"
        vllm_state.vllm_healthy = False
        vllm_state.vllm_probe_error = "no_vllm_base"
        return

    bare_main = normalize_openai_compatible_base(s.vllm_base_url)

    resolved = await _resolve_openai_api_base(bare_main, headers)
    vllm_state.resolved_api_base = resolved

    intent_raw = (s.vllm_intent_base_url or "").strip()
    main_norm = s.vllm_base_url.strip().rstrip("/")
    if intent_raw and intent_raw.rstrip("/") != main_norm:
        ibare = normalize_openai_compatible_base(intent_raw)
        vllm_state.resolved_intent_api_base = await _resolve_openai_api_base(ibare, headers)

    api_root = resolved if resolved else f"{bare_main}/v1"

    model = s.vllm_planner_model
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
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as c:
            r = await c.post(f"{api_root}/chat/completions", json=body, headers=headers)
            r.raise_for_status()
            data = r.json() or {}
        refined = _api_base_from_request_url(str(r.url))
        if refined:
            vllm_state.resolved_api_base = refined
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

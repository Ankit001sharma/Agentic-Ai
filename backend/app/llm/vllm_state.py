"""Module-level vLLM probe results (set at app startup in main lifespan)."""

from __future__ import annotations

# "native" | "json" — how tool calls are encoded
vllm_tool_mode: str = "json"
vllm_healthy: bool = False
vllm_probe_error: str | None = None

# After probe: OpenAI-compatible api_base URLs ending in /v1 (redirects applied, e.g. http→https).
resolved_api_base: str | None = None
resolved_intent_api_base: str | None = None

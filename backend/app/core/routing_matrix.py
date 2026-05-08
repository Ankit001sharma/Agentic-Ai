"""Model selection matrix used by ModelRoutingAgent."""

from __future__ import annotations

from app.core.config import get_settings

# Per-tier ordered preference list (cheap first, with a pro upgrade path)
TIER_PREFERENCE: dict[str, list[str]] = {
    "free": ["gpt-4o-mini"],
    "pro": [
        "gpt-4o-mini",
        "claude-3-5-haiku-latest",
        "claude-3-5-sonnet-latest",
        "gpt-4o",
    ],
    "enterprise": [
        "claude-3-5-sonnet-latest",
        "gpt-4o",
        "claude-3-5-haiku-latest",
        "gpt-4o-mini",
    ],
}

# When sensitivity == "high", prefer the locally hosted vLLM (Nemotron) configured
# via VLLM_BASE_URL / VLLM_PLANNER_MODEL — falls back to the per-tier list if vLLM
# is unavailable.
SENSITIVE_PREFERENCE: list[str] = []


def select_model(
    tier: str,
    requested: str | None,
    sensitivity: str,
    allowed: list[str] | None = None,
) -> tuple[list[str], str]:
    """Return (fallback_chain, primary_choice) honoring sensitivity + tier + OPA-allowlist."""
    settings = get_settings()
    sensitivity = (sensitivity or "normal").lower()

    if sensitivity == "high":
        candidates = list(SENSITIVE_PREFERENCE)
    else:
        candidates = list(TIER_PREFERENCE.get(tier, TIER_PREFERENCE["free"]))
    vm = settings.vllm_assistant_model or settings.vllm_planner_model
    if settings.vllm_base_url and vm:
        candidates = [vm] + [c for c in candidates if c != vm]

    if requested and requested in candidates:
        candidates = [requested] + [m for m in candidates if m != requested]

    if allowed:
        candidates = [m for m in candidates if m in allowed] or candidates

    if not candidates:
        candidates = [settings.default_model]
    return candidates, candidates[0]

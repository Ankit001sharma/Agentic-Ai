"""Task classifier + cost-aware smart routing.

Phase-1 implementation: heuristic classification (cheap, deterministic, easy to
demo).  Production would swap this for an embedding classifier or small LLM.

Outputs two signals consumed by `select_model_smart`:
- `task`:        chat | coding | analysis | summarization | creative | classification
- `complexity`:  low | medium | high
"""

from __future__ import annotations

import re
from typing import Any

from app.core.config import get_settings

# ----------------------------------------------------------------------
# 1. Task classification (heuristic)
# ----------------------------------------------------------------------

_TASK_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "coding",
        re.compile(
            r"(?i)\b(code|program|function|class|method|api|sdk|bug|stack\s*trace|"
            r"refactor|unit\s+test|regex|sql\s+query|python|javascript|typescript|"
            r"java|rust|golang|c\+\+|kubernetes\s+manifest|terraform)\b"
        ),
    ),
    (
        "analysis",
        re.compile(
            r"(?i)\b(analyz?e|compare|evaluate|root\s+cause|trade[\s-]?off|pros\s+and\s+cons|"
            r"assess|reason\s+about|why\s+does|explain\s+why)\b"
        ),
    ),
    (
        "summarization",
        re.compile(r"(?i)\b(summari[sz]e|tl;?dr|condense|brief\s+summary|key\s+points)\b"),
    ),
    (
        "creative",
        re.compile(
            r"(?i)\b(write\s+a\s+(poem|story|song|ad|tagline)|brainstorm|creative\s+ideas|"
            r"marketing\s+copy|tagline|slogan)\b"
        ),
    ),
    (
        "classification",
        re.compile(r"(?i)\b(classify|categor(?:y|ize|ise)|label|sentiment|spam\s+or\s+ham)\b"),
    ),
]


def classify_task(prompt: str) -> str:
    if not prompt:
        return "chat"
    for label, pat in _TASK_PATTERNS:
        if pat.search(prompt):
            return label
    return "chat"


# ----------------------------------------------------------------------
# 2. Complexity scoring (token-budget proxy)
# ----------------------------------------------------------------------

_COMPLEX_KEYWORDS = re.compile(
    r"(?i)\b(architect|design\s+a\s+system|end[\s-]?to[\s-]?end|step[\s-]?by[\s-]?step|"
    r"detailed\s+plan|reason\s+through|prove|derive|formal\s+proof|"
    r"comprehensive|multi[\s-]?step)\b"
)


def classify_complexity(prompt: str) -> str:
    if not prompt:
        return "low"
    n = len(prompt)
    words = prompt.split()
    if _COMPLEX_KEYWORDS.search(prompt) or n > 1200 or len(words) > 220:
        return "high"
    if n > 350 or len(words) > 70:
        return "medium"
    return "low"


# ----------------------------------------------------------------------
# 3. Smart routing matrix
#    Maps (task, complexity) → ordered preference list of models.
#    Cheap models first; high-complexity bumps the strong model to the front.
# ----------------------------------------------------------------------

# Strong models per family (used for high-complexity work).
_STRONG = ["claude-3-5-sonnet-latest", "gpt-4o"]
# Cheap, fast models (used for low-complexity / cost-aware routing).
_CHEAP = ["gpt-4o-mini", "claude-3-5-haiku-latest"]
# Local / private model for sensitive workloads.
_LOCAL: list[str] = []  # override via TASK_PREFERENCE or vllm_first chain when configured

# Coding tasks tend to favor Claude Sonnet / GPT-4o; cheap fallback for trivial snippets.
TASK_PREFERENCE: dict[str, dict[str, list[str]]] = {
    "coding": {
        "low": ["gpt-4o-mini", "claude-3-5-haiku-latest", "claude-3-5-sonnet-latest", "gpt-4o"],
        "medium": ["claude-3-5-sonnet-latest", "gpt-4o", "gpt-4o-mini"],
        "high": ["claude-3-5-sonnet-latest", "gpt-4o", "gpt-4o-mini"],
    },
    "analysis": {
        "low": ["gpt-4o-mini", "claude-3-5-haiku-latest", "claude-3-5-sonnet-latest"],
        "medium": ["claude-3-5-sonnet-latest", "gpt-4o", "gpt-4o-mini"],
        "high": ["gpt-4o", "claude-3-5-sonnet-latest"],
    },
    "summarization": {
        "low": ["gpt-4o-mini", "claude-3-5-haiku-latest"],
        "medium": ["gpt-4o-mini", "claude-3-5-haiku-latest", "claude-3-5-sonnet-latest"],
        "high": ["claude-3-5-sonnet-latest", "gpt-4o"],
    },
    "creative": {
        "low": ["gpt-4o-mini", "claude-3-5-haiku-latest"],
        "medium": ["claude-3-5-sonnet-latest", "gpt-4o-mini"],
        "high": ["claude-3-5-sonnet-latest", "gpt-4o"],
    },
    "classification": {
        "low": ["gpt-4o-mini", "claude-3-5-haiku-latest"],
        "medium": ["gpt-4o-mini", "claude-3-5-haiku-latest"],
        "high": ["claude-3-5-sonnet-latest", "gpt-4o-mini"],
    },
    "chat": {
        "low": ["gpt-4o-mini", "claude-3-5-haiku-latest"],
        "medium": ["gpt-4o-mini", "claude-3-5-sonnet-latest"],
        "high": ["claude-3-5-sonnet-latest", "gpt-4o"],
    },
}


def _vllm_preferred_chain(settings: Any) -> list[str] | None:
    """If vLLM is configured, prefer vLLM model id, then default cloud (if allowed)."""
    if not settings.vllm_base_url or not (settings.vllm_assistant_model or settings.vllm_planner_model):
        return None
    m = settings.vllm_assistant_model or settings.vllm_planner_model
    chain = [m]
    if settings.default_model and settings.default_model not in chain and settings.allow_cloud_fallback:
        chain.append(settings.default_model)
    return chain


def select_model_smart(
    tier: str,
    requested: str | None,
    sensitivity: str,
    task: str,
    complexity: str,
    allowed: list[str] | None = None,
) -> tuple[list[str], str, dict]:
    """Cost-aware, task-aware model selection.

    Returns (fallback_chain, primary, audit) where audit explains the choice.
    """
    settings = get_settings()
    sensitivity = (sensitivity or "normal").lower()
    tier = (tier or "free").lower()
    task = (task or "chat").lower()
    complexity = (complexity or "low").lower()

    vllm_first = _vllm_preferred_chain(settings)

    # 1. Hard override: sensitive workload -> local-only model
    if sensitivity == "high":
        candidates = list(_LOCAL) if vllm_first is None else [vllm_first[0]] + list(_LOCAL)
        reason = "sensitivity=high → local+pref"
    else:
        # 2. Look up task/complexity preference; prepend vLLM if configured
        base = list(TASK_PREFERENCE.get(task, TASK_PREFERENCE["chat"]).get(complexity, []))
        if vllm_first:
            candidates = list(vllm_first) + [c for c in base if c not in vllm_first]
        else:
            candidates = base

        # 3. Tier gate: free tier never gets a strong model except when complexity demands it,
        #    and even then we only allow gpt-4o-mini family.
        if tier == "free":
            candidates = [m for m in candidates if m in _CHEAP + _LOCAL]
            if not candidates:
                candidates = list(_CHEAP)
        elif tier == "pro":
            # pro: drop the most expensive (gpt-4o) for low complexity to save cost
            if complexity == "low":
                candidates = [m for m in candidates if m != "gpt-4o"] or candidates
        # enterprise: keep full list

        reason = f"tier={tier} task={task} complexity={complexity}"

    # 4. Honour caller's explicit request only if it is in the allowed candidate set
    if requested and requested in candidates:
        candidates = [requested] + [m for m in candidates if m != requested]

    # 5. Honour OPA-derived allowlist
    if allowed:
        filtered = [m for m in candidates if m in allowed]
        if filtered:
            candidates = filtered

    if not candidates:
        candidates = [settings.default_model]

    audit = {
        "task": task,
        "complexity": complexity,
        "tier": tier,
        "sensitivity": sensitivity,
        "reason": reason,
        "chain": candidates,
    }
    return candidates, candidates[0], audit

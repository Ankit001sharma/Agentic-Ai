"""Normalize OpenAI-compatible base URLs (vLLM, etc.) from env or pasted endpoints."""

from __future__ import annotations


def normalize_openai_compatible_base(raw: str) -> str:
    """Strip common path suffixes so we keep only scheme://host[:port].

    Accepts:
    - https://host
    - http://host:8000
    - …/v1/chat/completions (full chat URL pasted from docs or Postman)
    - …/v1 (trailing API prefix)
    """
    u = raw.strip().rstrip("/")
    if not u:
        return u
    for suffix in ("/v1/chat/completions", "/chat/completions"):
        if u.endswith(suffix):
            u = u[: -len(suffix)].rstrip("/")
    while u.endswith("/v1"):
        u = u[:-3].rstrip("/")
    return u

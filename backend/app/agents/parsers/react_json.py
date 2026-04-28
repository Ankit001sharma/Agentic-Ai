"""JSON ReAct parser for vLLM JSON-mode tool fallback."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ReactParseResult:
    thought: str
    tool: str | None
    args: dict[str, Any]
    final: dict[str, Any] | None
    raw: str


def parse_react_json(text: str) -> ReactParseResult | None:
    """Parse optional JSON in assistant message. Supports
    { "thought", "tool", "args" } or { "final": { "verdict", "confidence", ... } }.
    """
    if not text or not text.strip():
        return None
    t = text.strip()
    if "```" in t:
        m = re.search(r"```(?:json)?\s*([\s\S]+?)```", t, re.IGNORECASE)
        if m:
            t = m.group(1).strip()
    try:
        data = json.loads(t)
    except json.JSONDecodeError:
        o = t.find("{")
        c = t.rfind("}")
        if o >= 0 and c > o:
            try:
                data = json.loads(t[o : c + 1])
            except json.JSONDecodeError:
                return None
        else:
            return None
    if not isinstance(data, dict):
        return None
    thought = str(data.get("thought", ""))
    if "final" in data and isinstance(data["final"], dict):
        return ReactParseResult(
            thought=thought,
            tool=None,
            args={},
            final=data["final"],
            raw=t,
        )
    tool = data.get("tool")
    args = data.get("args")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}
    if not isinstance(args, dict):
        args = {}
    return ReactParseResult(
        thought=thought,
        tool=str(tool) if tool else None,
        args=args,
        final=None,
        raw=t,
    )

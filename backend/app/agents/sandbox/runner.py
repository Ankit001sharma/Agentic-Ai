"""Isolated code execution: optional HTTP sidecar; safe local fallback (math-only)."""

from __future__ import annotations

import ast
import operator
import re
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("sandbox")

_ALLOWED = re.compile(r"^(python|py)$", re.IGNORECASE)
_BINOPS: dict[type, object] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}


def _ev(node: Any) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        f = _BINOPS[type(node.op)]
        return float(f(_ev(node.left), _ev(node.right)))  # type: ignore[operator, arg-type]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_ev(node.operand)  # type: ignore[arg-type]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
        return _ev(node.operand)  # type: ignore[arg-type]
    raise ValueError("only numeric expr allowed")


async def run_code_in_sandbox(code: str, language: str = "python", timeout: float = 20.0) -> str:
    s = get_settings()
    if not _ALLOWED.match((language or "python").strip()):
        return f"error: language not allowed: {language}"
    code = (code or "")[:32_000]
    url = (s.code_sandbox_url or "").rstrip("/") + "/run"
    if s.code_sandbox_url and "disabled" not in s.code_sandbox_url.lower():
        try:
            async with httpx.AsyncClient(timeout=timeout) as c:
                r = await c.post(
                    url,
                    json={"code": code, "language": "python", "timeout": min(timeout, 20)},
                )
                r.raise_for_status()
                d = r.json() or {}
                return str(d.get("stdout", d.get("result", d)))
        except Exception as e:  # noqa: BLE001
            log.warning("sandbox_service_failed", error=str(e))
    try:
        t = ast.parse(code, mode="eval")
        v = _ev(t.body)  # type: ignore[union-attr, arg-type, assignment]
        return str(int(v) if v == int(v) else v)
    except Exception as e:  # noqa: BLE001
        return f"error: {e}"

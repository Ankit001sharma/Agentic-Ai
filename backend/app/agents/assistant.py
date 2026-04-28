"""AssistantAgent — optional post-allow tool-using phase (v2 uses llm_invoke + self-correct in graph)."""

from __future__ import annotations

import ast
import operator

import httpx

from app.core.config import get_settings
from app.core.policies import OPAClient
from app.core.logging import get_logger
from app.schemas.sentinel import ScanState, Verdict

log = get_logger("agent.assistant")

_OPA = OPAClient()

_SAFE_BINOPS: dict[type, object] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Mod: operator.mod,
}


def _eval_safe(node: object) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_BINOPS:
        return _SAFE_BINOPS[type(node.op)](_eval_safe(node.left), _eval_safe(node.right))  # type: ignore[operator, arg-type]
    if isinstance(node, ast.UnaryOp) and type(node.op) in (ast.USub, ast.UAdd):
        v = _eval_safe(node.operand)  # type: ignore[arg-type]
        if isinstance(node.op, ast.USub):
            return -v
        return v
    msg = f"unsafe expr: {type(node)}"
    raise ValueError(msg)


def safe_calculator(expr: str) -> str:
    t = (expr or "").strip()[:200]
    if not t:
        return "0"
    try:
        tree = ast.parse(t, mode="eval")
        v = _eval_safe(tree.body)
        return str(int(v) if v == int(v) else v)
    except Exception as e:  # noqa: BLE001
        return f"error: {e}"


async def tool_opa_for_tool(state: ScanState, tool: str) -> bool:
    user = {
        "id": state.user.user_id,
        "tier": state.user.tier,
        "region": state.user.region,
        "role": state.user.role,
    }
    allowed = await _OPA.allowed_tools(
        user, workspace_dir=get_settings().assistant_workspace
    )
    return tool in allowed


async def run(state: ScanState) -> ScanState:
    """Placeholder for RAG/web/code; core chat response still comes from llm_invoke in graph v2."""
    if state.verdict not in (Verdict.ALLOW, Verdict.MASK):
        return state
    s = get_settings()
    for ev in (state.assistant_steps or []):
        state.audit_events.append({"agent": "assistant", "ev": ev})
    if s.web_search_url and "web_search" in (state.assistant_steps or []):
        pass  # would call web_search_url; stub
    return state

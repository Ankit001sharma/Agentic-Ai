"""Async OPA HTTP client wrapper."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger("opa")


class OPAClient:
    """Calls an Open Policy Agent sidecar at /v1/data/<package>/<rule>."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or get_settings().opa_url).rstrip("/")

    async def evaluate(
        self,
        package: str = "sentinel",
        rule: str = "allow",
        input_doc: dict[str, Any] | None = None,
        timeout: float = 2.0,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/v1/data/{package}/{rule}"
        body = {"input": input_doc or {}}
        try:
            async with httpx.AsyncClient(timeout=timeout) as c:
                r = await c.post(url, json=body)
                r.raise_for_status()
                data = r.json() or {}
                return data
        except Exception as e:  # noqa: BLE001
            log.warning("opa_unavailable", error=str(e))
            # Fail-open in MVP: trust the Decision Gate to enforce.
            return {"result": True, "_offline": True}

    async def decide(
        self,
        user: dict[str, Any],
        model: str,
        verdict: str,
        sensitivity: str = "normal",
    ) -> dict[str, Any]:
        """High-level decision: returns {allow: bool, reasons: [...]}."""
        input_doc = {
            "user": user,
            "model": model,
            "verdict": verdict,
            "sensitivity": sensitivity,
        }
        # Fetch the boolean allow rule
        r = await self.evaluate("sentinel", "allow", input_doc)
        allow = bool(r.get("result", True))
        reasons_resp = await self.evaluate("sentinel", "reasons", input_doc)
        reasons = reasons_resp.get("result") or []
        return {"allow": allow, "reasons": reasons, "_offline": r.get("_offline", False)}

    async def allowed_models(self, user: dict[str, Any]) -> list[str]:
        try:
            r = await self.evaluate("sentinel/models", "allowed_models", {"user": user})
            return list(r.get("result") or [])
        except Exception:  # noqa: BLE001
            return []

    async def decide_access(
        self,
        user: dict[str, Any],
        resource: str | None,
        action: str,
        intent: str,
    ) -> dict[str, Any]:
        input_doc: dict[str, Any] = {
            "user": user,
            "action": action,
            "intent": intent,
        }
        if resource:
            input_doc["resource"] = resource
        r = await self.evaluate("sentinel/access", "allow", input_doc)
        allow = bool(r.get("result", True))
        reasons_resp = await self.evaluate("sentinel/access", "reasons", input_doc)
        reasons = reasons_resp.get("result") or []
        return {"allow": allow, "reasons": reasons, "_offline": r.get("_offline", False)}

    async def decide_compliance(
        self, user: dict[str, Any], data_class: str, request_meta: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        input_doc = {
            "user": user,
            "data_class": data_class,
            "request": request_meta or {},
        }
        r = await self.evaluate("sentinel/compliance", "allow", input_doc)
        return {
            "allow": bool(r.get("result", True)),
            "reasons": (await self.evaluate("sentinel/compliance", "reasons", input_doc)).get("result")
            or [],
        }

    async def decide_intent_rules(
        self, user: dict[str, Any], intent: str, sensitivity: str
    ) -> dict[str, Any]:
        input_doc = {"user": user, "intent": intent, "sensitivity": sensitivity}
        d = await self.evaluate("sentinel/intent", "deny_outright", input_doc)
        rh = await self.evaluate("sentinel/intent", "require_human_review", input_doc)
        lm = await self.evaluate("sentinel/intent", "require_local_model", input_doc)
        rate = await self.evaluate("sentinel/intent", "rate_limit_class", input_doc)
        return {
            "deny_outright": bool(d.get("result", False)),
            "require_human_review": bool(rh.get("result", False)),
            "require_local_model": bool(lm.get("result", False)),
            "rate_limit_class": rate.get("result") or "normal",
        }

    async def allowed_tools(
        self, user: dict[str, Any], workspace_dir: str | None = None
    ) -> set[str]:
        input_doc: dict[str, Any] = {"user": user}
        if workspace_dir:
            input_doc["workspace_dir"] = workspace_dir
        try:
            r = await self.evaluate("sentinel/tools", "allow_tool", input_doc)
            res = r.get("result")
            if isinstance(res, list):
                return set(res)
            if res is not None and not isinstance(res, (bool, int, str)):
                return set(res)  # set from OPA
            return set()
        except Exception:  # noqa: BLE001
            return {
                "web_search",
                "rag_query",
                "calculator",
                "file_read",
                "code_exec_sandbox",
                "http_get",
                "sql_query_ro",
            }

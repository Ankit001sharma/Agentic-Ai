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
        *,
        offline_result: Any = True,
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
            # Fail-open for *allow* rules (True); deny/restrict rules must default False when offline.
            return {"result": offline_result, "_offline": True}

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
        r = await self.evaluate("sentinel", "allow", input_doc, offline_result=True)
        allow = bool(r.get("result", True))
        reasons_resp = await self.evaluate("sentinel", "reasons", input_doc, offline_result=[])
        reasons = reasons_resp.get("result") or []
        return {"allow": allow, "reasons": reasons, "_offline": r.get("_offline", False)}

    async def allowed_models(self, user: dict[str, Any]) -> list[str]:
        try:
            r = await self.evaluate(
                "sentinel/models", "allowed_models", {"user": user}, offline_result=[]
            )
            res = r.get("result")
            if isinstance(res, list):
                return list(res)
            return []
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
        r = await self.evaluate("sentinel/access", "allow", input_doc, offline_result=True)
        allow = bool(r.get("result", True))
        reasons_resp = await self.evaluate("sentinel/access", "reasons", input_doc, offline_result=[])
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
        r = await self.evaluate("sentinel/compliance", "allow", input_doc, offline_result=True)
        return {
            "allow": bool(r.get("result", True)),
            "reasons": (
                await self.evaluate("sentinel/compliance", "reasons", input_doc, offline_result=[])
            ).get("result")
            or [],
        }

    async def decide_intent_rules(
        self, user: dict[str, Any], intent: str, sensitivity: str
    ) -> dict[str, Any]:
        input_doc = {"user": user, "intent": intent, "sensitivity": sensitivity}
        d = await self.evaluate("sentinel/intent", "deny_outright", input_doc, offline_result=False)
        rh = await self.evaluate(
            "sentinel/intent", "require_human_review", input_doc, offline_result=False
        )
        lm = await self.evaluate(
            "sentinel/intent", "require_local_model", input_doc, offline_result=False
        )
        rate = await self.evaluate(
            "sentinel/intent", "rate_limit_class", input_doc, offline_result="normal"
        )
        return {
            "deny_outright": bool(d.get("result", False)),
            "require_human_review": bool(rh.get("result", False)),
            "require_local_model": bool(lm.get("result", False)),
            "rate_limit_class": rate.get("result") or "normal",
        }

    async def check_tool(
        self,
        input_doc: dict[str, Any],
        tool_id: str,
    ) -> tuple[bool, list[str]]:
        """Check if user is allowed to invoke a specific pipeline tool.

        Authorization MUST fail closed: when OPA is unreachable or returns
        a malformed response, we deny rather than allow. Returning the
        previous fail-open behaviour silently bypassed every role gate
        whenever the OPA sidecar restarted.

        Returns (allowed: bool, reasons: list[str]).
        """
        # offline_result=[] → if OPA is down, treat the allowed-tool set as
        # empty, which makes membership checks fail (deny).
        r = await self.evaluate("sentinel/tools", "allow_tool", input_doc, offline_result=[])
        offline = bool(r.get("_offline"))
        result = r.get("result")

        # OPA incremental `contains` rules return a list/set of allowed IDs.
        # Anything else (bool, str, None) is treated as "no membership info"
        # and denied — fail-closed for security-sensitive policies.
        if isinstance(result, (list, set)):
            allowed = tool_id in result
        else:
            allowed = False

        reasons: list[str] = []
        if not allowed:
            if offline:
                reasons.append(
                    f"OPA unavailable — denying tool '{tool_id}' (fail-closed)."
                )
            else:
                reasons.append(
                    f"User role '{input_doc.get('user', {}).get('role')}' "
                    f"not permitted for tool '{tool_id}'"
                )
        return allowed, reasons

    async def allowed_tools(
        self, user: dict[str, Any], workspace_dir: str | None = None
    ) -> set[str]:
        """Best-effort list of tool IDs the user can call right now.

        Used by dashboards and quickstart helpers (NOT enforcement). If OPA
        is unreachable we return a small set of read-only IDs the UI can
        still surface; enforcement always goes through `check_tool` which
        fails closed.
        """
        input_doc: dict[str, Any] = {"user": user}
        if workspace_dir:
            input_doc["workspace_dir"] = workspace_dir
        try:
            r = await self.evaluate("sentinel/tools", "allow_tool", input_doc, offline_result=[])
            res = r.get("result")
            if isinstance(res, list):
                return set(res)
            if isinstance(res, set):
                return set(res)
            return set()
        except Exception:  # noqa: BLE001
            # Tool IDs that match the canonical names in backend/tools.yaml —
            # only the read-only / search ones, so the dashboard can render a
            # safe partial list when OPA is offline.
            return {
                "search_web",
                "search_docs",
                "query_miniorange_docs",
                "list_miniorange_plugins",
                "get_miniorange_plugin",
            }

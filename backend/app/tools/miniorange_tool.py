"""miniOrange documentation tools: keyword search over the local knowledge base with optional Mistral AI synthesis."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import time
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.tools.base import ToolExecutor, ToolResult

log = get_logger("tools.miniorange")

# Module-level lazy cache — populated on first call, never reloaded mid-process.
_docs: list[dict[str, Any]] | None = None
_guides: list[dict[str, Any]] | None = None


# region agent log
def _debug_log(run_id: str, hypothesis_id: str, location: str, message: str, data: dict) -> None:
    try:
        payload = {
            "sessionId": "caa63e",
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with open("debug-caa63e.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
# endregion


def _data_dir() -> Path:
    s = get_settings()
    d = s.miniorange_data_dir.strip()
    if not d:
        raise RuntimeError("MINIORANGE_DATA_DIR is not configured")
    return Path(d)


def _get_docs() -> list[dict[str, Any]]:
    global _docs
    if _docs is None:
        path = _data_dir() / "miniorange_docs.json"
        with open(path, encoding="utf-8") as f:
            _docs = json.load(f)
    return _docs


def _get_guides() -> list[dict[str, Any]]:
    global _guides
    if _guides is None:
        path = _data_dir() / "guides.json"
        with open(path, encoding="utf-8") as f:
            _guides = json.load(f)
    return _guides


def _search_docs_sync(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """Keyword scoring: title match=5, url match=3, content match=1. Returns top_k docs."""
    docs = _get_docs()
    query_lower = query.lower()
    terms = [t for t in query_lower.split() if len(t) > 1] or [query_lower]

    scored: list[tuple[int, dict[str, Any]]] = []
    for doc in docs:
        score = 0
        title = doc.get("title", "").lower()
        url = doc.get("url", "").lower()
        content = doc.get("content", "").lower()
        for term in terms:
            if term in title:
                score += 5
            if term in url:
                score += 3
            if term in content:
                score += 1
        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scored[:top_k]]


def _list_plugins_sync() -> list[str]:
    docs = _get_docs()
    seen: set[str] = set()
    titles: list[str] = []
    for doc in docs:
        title = doc.get("title")
        if title and title not in seen:
            titles.append(title)
            seen.add(title)
    return sorted(titles)


def _get_guide_sync(service: str) -> dict[str, Any] | None:
    guides = _get_guides()
    service_lower = service.lower()
    for guide in guides:
        if service_lower in guide.get("service", "").lower():
            return guide
    return None


class QueryMiniOrangeDocsExecutor(ToolExecutor):
    """Search miniOrange docs by keyword; optionally synthesize with Mistral."""

    async def execute(
        self,
        args: dict[str, Any],
        *,
        idempotency_key: str,
        simulate: bool = False,
    ) -> ToolResult:
        query = _extract_query_arg(args)
        top_k: int = int(args.get("top_k") or 3)
        # region agent log
        _debug_log(
            idempotency_key,
            "H4",
            "miniorange_tool.py:QueryMiniOrangeDocsExecutor.execute",
            "miniorange query extraction",
            {
                "args_keys": sorted(list(args.keys())),
                "query_len": len(query),
                "top_k": top_k,
            },
        )
        # endregion

        if not query:
            # region agent log
            _debug_log(
                idempotency_key,
                "H6",
                "miniorange_tool.py:QueryMiniOrangeDocsExecutor.execute:empty_query",
                "miniorange fail empty query",
                {"args_keys": sorted(list(args.keys()))},
            )
            # endregion
            return ToolResult.fail(
                "query_miniorange_docs",
                code="TOOL_INVALID_ARGS",
                message="query must not be empty",
                retryable=False,
                user_facing=True,
                idempotency_key=idempotency_key,
            )

        if simulate:
            return ToolResult.ok(
                "query_miniorange_docs",
                {"simulated": True, "query": query},
                simulated=True,
                idempotency_key=idempotency_key,
            )

        s = get_settings()
        if not s.miniorange_data_dir:
            # region agent log
            _debug_log(
                idempotency_key,
                "H6",
                "miniorange_tool.py:QueryMiniOrangeDocsExecutor.execute:config_error",
                "miniorange config missing",
                {"miniorange_data_dir_set": bool(s.miniorange_data_dir)},
            )
            # endregion
            return ToolResult.fail(
                "query_miniorange_docs",
                code="TOOL_CONFIG_ERROR",
                message="MINIORANGE_DATA_DIR is not configured",
                retryable=False,
                user_facing=True,
                idempotency_key=idempotency_key,
            )

        try:
            loop = asyncio.get_running_loop()
            top_docs: list[dict[str, Any]] = await loop.run_in_executor(
                None, _search_docs_sync, query, top_k
            )
        except FileNotFoundError as exc:
            # region agent log
            _debug_log(
                idempotency_key,
                "H6",
                "miniorange_tool.py:QueryMiniOrangeDocsExecutor.execute:search_error",
                "miniorange search exception",
                {"error": str(exc)[:200]},
            )
            # endregion
            return ToolResult.fail(
                "query_miniorange_docs",
                code="MINIORANGE_DATA_MISSING",
                message=(
                    "The miniOrange knowledge base files are not present at "
                    f"MINIORANGE_DATA_DIR='{s.miniorange_data_dir}'. "
                    "Please add miniorange_docs.json and guides.json to that directory."
                ),
                retryable=False,
                user_facing=True,
                idempotency_key=idempotency_key,
            )
        except Exception as exc:
            # region agent log
            _debug_log(
                idempotency_key,
                "H6",
                "miniorange_tool.py:QueryMiniOrangeDocsExecutor.execute:search_error",
                "miniorange search exception",
                {"error": str(exc)[:200]},
            )
            # endregion
            return ToolResult.fail(
                "query_miniorange_docs",
                code="MINIORANGE_SEARCH_ERROR",
                message=f"Failed to search miniOrange documentation: {exc}",
                retryable=True,
                user_facing=True,
                idempotency_key=idempotency_key,
            )

        if not top_docs:
            # region agent log
            _debug_log(
                idempotency_key,
                "H6",
                "miniorange_tool.py:QueryMiniOrangeDocsExecutor.execute:no_results",
                "miniorange no docs found",
                {"query_len": len(query)},
            )
            # endregion
            return ToolResult.ok(
                "query_miniorange_docs",
                {"answer": None, "results": [], "query": query},
                idempotency_key=idempotency_key,
            )

        answer: str | None = None
        if top_docs:
            try:
                from app.llm.litellm_client import acomplete  # local import avoids circular

                context = ""
                for doc in top_docs:
                    context += f"--- {doc.get('title', '')} ({doc.get('url', '')}) ---\n"
                    context += doc.get("content", "")[:12000]
                    context += "\n\n"

                synthesis_messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are a miniOrange technical support engineer. "
                            "Your job is to answer the user's question using the documentation content provided.\n\n"
                            "STRICT RULES:\n"
                            "1. Extract and present the ACTUAL information from the documentation — features, steps, config, concepts.\n"
                            "2. NEVER just describe what a doc is about or say 'refer to the docs'. Give the real content.\n"
                            "3. If there are setup steps, list them. If there are config options, show them. If there are key concepts, explain them.\n"
                            "4. Only add a documentation link at the very END as 'For more details: <url>' — never as the main answer.\n"
                            "5. Format in Markdown with headings, bullet points, and code blocks where relevant.\n"
                            "6. Keep the answer focused and informative, 150–400 words."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Documentation content:\n{context}\n\nQuestion: {query}",
                    },
                ]
                text, _model, _fallback = await acomplete(
                    synthesis_messages, timeout=20.0, max_tokens=1024
                )
                if text.strip() and not text.startswith("[stub-llm"):
                    answer = text.strip()
            except Exception as exc:
                log.warning("miniorange_synthesis_failed", error=str(exc))

        results = [
            {
                "title": d.get("title"),
                "url": d.get("url"),
                "module": d.get("module"),
                "snippet": (d.get("content") or "")[:400].strip(),
            }
            for d in top_docs
        ]
        # region agent log
        _debug_log(
            idempotency_key,
            "H6",
            "miniorange_tool.py:QueryMiniOrangeDocsExecutor.execute:success",
            "miniorange success",
            {"results_count": len(results), "has_answer": bool(answer)},
        )
        # endregion
        return ToolResult.ok(
            "query_miniorange_docs",
            {"answer": answer, "results": results, "query": query},
            idempotency_key=idempotency_key,
        )


def _extract_query_arg(args: dict[str, Any]) -> str:
    """Extract query text from common aliases and nested argument shapes."""
    candidates: list[Any] = [
        args.get("query"),
        args.get("text"),
        args.get("prompt"),
        args.get("question"),
    ]
    nested = args.get("arguments")
    if isinstance(nested, dict):
        candidates.extend(
            [
                nested.get("query"),
                nested.get("text"),
                nested.get("prompt"),
                nested.get("question"),
            ]
        )
    for value in candidates:
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned:
                return cleaned
    return ""


class ListMiniOrangePluginsExecutor(ToolExecutor):
    """Return sorted list of all miniOrange plugin titles from the docs index."""

    async def execute(
        self,
        args: dict[str, Any],
        *,
        idempotency_key: str,
        simulate: bool = False,
    ) -> ToolResult:
        if simulate:
            return ToolResult.ok(
                "list_miniorange_plugins",
                {"simulated": True, "plugins": []},
                simulated=True,
                idempotency_key=idempotency_key,
            )

        s = get_settings()
        if not s.miniorange_data_dir:
            return ToolResult.fail(
                "list_miniorange_plugins",
                code="TOOL_CONFIG_ERROR",
                message="MINIORANGE_DATA_DIR is not configured",
                retryable=False,
                user_facing=True,
                idempotency_key=idempotency_key,
            )

        try:
            loop = asyncio.get_running_loop()
            plugins: list[str] = await loop.run_in_executor(None, _list_plugins_sync)
        except Exception as exc:
            return ToolResult.fail(
                "list_miniorange_plugins",
                code="MINIORANGE_LIST_ERROR",
                message=str(exc),
                retryable=True,
                user_facing=False,
                idempotency_key=idempotency_key,
            )

        return ToolResult.ok(
            "list_miniorange_plugins",
            {"plugins": plugins, "count": len(plugins)},
            idempotency_key=idempotency_key,
        )


class GetMiniOrangePluginExecutor(ToolExecutor):
    """Return auth type, required credentials, and setup walkthrough for a service."""

    async def execute(
        self,
        args: dict[str, Any],
        *,
        idempotency_key: str,
        simulate: bool = False,
    ) -> ToolResult:
        service: str = args.get("service", "").strip()
        if not service:
            return ToolResult.fail(
                "get_miniorange_plugin",
                code="TOOL_INVALID_ARGS",
                message="service must not be empty",
                retryable=False,
                user_facing=True,
                idempotency_key=idempotency_key,
            )

        if simulate:
            return ToolResult.ok(
                "get_miniorange_plugin",
                {"simulated": True, "service": service},
                simulated=True,
                idempotency_key=idempotency_key,
            )

        s = get_settings()
        if not s.miniorange_data_dir:
            return ToolResult.fail(
                "get_miniorange_plugin",
                code="TOOL_CONFIG_ERROR",
                message="MINIORANGE_DATA_DIR is not configured",
                retryable=False,
                user_facing=True,
                idempotency_key=idempotency_key,
            )

        try:
            loop = asyncio.get_running_loop()
            guide = await loop.run_in_executor(None, _get_guide_sync, service)
        except Exception as exc:
            return ToolResult.fail(
                "get_miniorange_plugin",
                code="MINIORANGE_GUIDE_ERROR",
                message=str(exc),
                retryable=True,
                user_facing=False,
                idempotency_key=idempotency_key,
            )

        if not guide:
            return ToolResult.fail(
                "get_miniorange_plugin",
                code="MINIORANGE_NOT_FOUND",
                message=f"No guide found for service '{service}'",
                retryable=False,
                user_facing=True,
                idempotency_key=idempotency_key,
            )

        return ToolResult.ok(
            "get_miniorange_plugin",
            {
                "service": guide.get("service"),
                "auth_type": guide.get("auth_type"),
                "requires": guide.get("requires", []),
                "description": guide.get("description", ""),
                "setup_steps": guide.get("setup_steps", []),
                "env_template": guide.get("env_template", {}),
            },
            idempotency_key=idempotency_key,
        )

"""Search tool executors: Tavily web search + Qdrant docs search."""

from __future__ import annotations

import asyncio
import threading
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.tools.base import ToolExecutor, ToolResult

log = get_logger("tools.search")

TAVILY_API_URL = "https://api.tavily.com/search"

# Lazy-loaded SentenceTransformer singleton. Loading this model from disk takes
# 1–3 seconds and allocates ~80 MB; it MUST NOT happen on every search_docs
# request. We load on first use and cache for the process lifetime.
_EMBEDDING_MODEL: Any = None
_EMBEDDING_MODEL_LOCK = threading.Lock()
_EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


def _get_embedding_model() -> Any:
    """Return the cached SentenceTransformer instance, loading it once."""
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is not None:
        return _EMBEDDING_MODEL
    with _EMBEDDING_MODEL_LOCK:
        if _EMBEDDING_MODEL is None:
            from sentence_transformers import SentenceTransformer  # type: ignore[import]

            log.info("embedding_model_loading", model=_EMBEDDING_MODEL_NAME)
            _EMBEDDING_MODEL = SentenceTransformer(_EMBEDDING_MODEL_NAME)
            log.info("embedding_model_loaded", model=_EMBEDDING_MODEL_NAME)
    return _EMBEDDING_MODEL


class SearchToolExecutor(ToolExecutor):
    """Web search via Tavily API."""

    async def execute(
        self,
        args: dict[str, Any],
        *,
        idempotency_key: str,
        simulate: bool = False,
    ) -> ToolResult:
        s = get_settings()
        query: str = args.get("query", "")
        max_results: int = args.get("max_results", 5)
        search_depth: str = args.get("search_depth", "basic")
        include_answer: bool = args.get("include_answer", True)

        if simulate:
            return ToolResult.ok(
                "search_web",
                {"simulated": True, "query": query},
                simulated=True,
                idempotency_key=idempotency_key,
            )

        if not s.tavily_api_key:
            return ToolResult.fail(
                "search_web",
                code="TOOL_CONFIG_ERROR",
                message="TAVILY_API_KEY is not configured",
                retryable=False,
                user_facing=True,
                idempotency_key=idempotency_key,
            )

        payload = {
            "api_key": s.tavily_api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_answer": include_answer,
        }

        try:
            async with httpx.AsyncClient(timeout=s.tool_search_timeout) as client:
                resp = await asyncio.wait_for(
                    client.post(TAVILY_API_URL, json=payload),
                    timeout=s.tool_search_timeout,
                )
            if resp.status_code == 200:
                data = resp.json()
                return ToolResult.ok(
                    "search_web",
                    {
                        "answer": data.get("answer"),
                        "results": data.get("results", [])[:max_results],
                        "query": query,
                    },
                    idempotency_key=idempotency_key,
                )
            return ToolResult.fail(
                "search_web",
                code=f"TAVILY_HTTP_{resp.status_code}",
                message=resp.text[:500],
                retryable=resp.status_code >= 500,
                user_facing=True,
                idempotency_key=idempotency_key,
            )
        except (httpx.TimeoutException, asyncio.TimeoutError):
            return ToolResult.fail(
                "search_web",
                code="TOOL_TIMEOUT",
                message="Tavily search timed out",
                retryable=True,
                user_facing=True,
                idempotency_key=idempotency_key,
            )


class DocsSearchExecutor(ToolExecutor):
    """Semantic search over internal docs via Qdrant."""

    async def execute(
        self,
        args: dict[str, Any],
        *,
        idempotency_key: str,
        simulate: bool = False,
    ) -> ToolResult:
        query: str = args.get("query", "")
        top_k: int = args.get("top_k", 5)
        collection: str = args.get("collection", "docs")

        if simulate:
            return ToolResult.ok(
                "search_docs",
                {"simulated": True, "query": query},
                simulated=True,
                idempotency_key=idempotency_key,
            )

        try:
            from qdrant_client import AsyncQdrantClient
            from qdrant_client.models import ScoredPoint

            from app.core.config import get_settings
            s = get_settings()
            qdrant_url = getattr(s, "qdrant_url", "http://qdrant:6333")

            # Embed query with cached sentence-transformers model. The model
            # load is offloaded to a worker thread on first call so we don't
            # block the event loop for 1–3 seconds.
            loop = asyncio.get_running_loop()
            model = await loop.run_in_executor(None, _get_embedding_model)
            vector = await loop.run_in_executor(None, model.encode, query)
            vector = vector.tolist()

            client = AsyncQdrantClient(url=qdrant_url)
            hits: list[ScoredPoint] = await client.search(
                collection_name=collection,
                query_vector=vector,
                limit=top_k,
            )
            results = [
                {"score": h.score, "payload": h.payload}
                for h in hits
            ]
            return ToolResult.ok(
                "search_docs",
                {"results": results, "query": query},
                idempotency_key=idempotency_key,
            )
        except ImportError:
            return ToolResult.fail(
                "search_docs",
                code="TOOL_DEPENDENCY_MISSING",
                message="qdrant_client or sentence-transformers not installed",
                retryable=False,
                user_facing=False,
                idempotency_key=idempotency_key,
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult.fail(
                "search_docs",
                code="QDRANT_ERROR",
                message=str(exc),
                retryable=True,
                user_facing=False,
                idempotency_key=idempotency_key,
            )

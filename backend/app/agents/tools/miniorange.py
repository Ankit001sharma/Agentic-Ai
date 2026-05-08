"""miniOrange supervisor tools — thin async wrappers for the Nemotron ReAct loop."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.agents.tools.base import ToolResult
from app.core.logging import get_logger
from app.schemas.sentinel import ScanState

log = get_logger("agents.tools.miniorange")


async def tool_query_miniorange_docs(query: str, state: ScanState) -> ToolResult:
    t0 = time.perf_counter()
    try:
        from app.core.config import get_settings
        from app.tools.miniorange_tool import _search_docs_sync

        s = get_settings()
        if not s.miniorange_data_dir:
            return ToolResult(
                ok=False,
                name="query_miniorange_docs",
                summary="MINIORANGE_DATA_DIR not configured",
                error="config_error",
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )

        loop = asyncio.get_running_loop()
        top_docs: list[dict[str, Any]] = await loop.run_in_executor(
            None, _search_docs_sync, query, 3
        )

        answer: str | None = None
        if top_docs and s.vllm_base_url:
            try:
                import litellm  # type: ignore[import]

                context = ""
                for doc in top_docs:
                    context += f"--- {doc.get('title', '')} ({doc.get('url', '')}) ---\n"
                    context += doc.get("content", "")[:10000]
                    context += "\n\n"
                resp = await litellm.acompletion(
                    model=f"openai/{s.vllm_planner_model}",
                    base_url=s.vllm_base_url,
                    api_key=s.vllm_api_key or "none",
                    timeout=15.0,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a miniOrange technical support engineer. Answer with code snippets and step-by-step instructions from the provided documentation. Format in Markdown.",
                        },
                        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
                    ],
                )
                answer = resp.choices[0].message.content
            except Exception as exc:
                log.warning("miniorange_vllm_synthesis_failed", error=str(exc))

        results = [
            {"title": d.get("title"), "url": d.get("url"), "module": d.get("module")}
            for d in top_docs
        ]
        suffix = " (synthesized)" if answer else ""
        return ToolResult(
            ok=True,
            name="query_miniorange_docs",
            summary=f"found={len(results)} docs for '{query[:60]}'{suffix}",
            data={"answer": answer, "results": results, "query": query},
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )
    except Exception as exc:
        return ToolResult(
            ok=False,
            name="query_miniorange_docs",
            summary=str(exc)[:500],
            error="miniorange_error",
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )


async def tool_list_miniorange_plugins(state: ScanState) -> ToolResult:
    t0 = time.perf_counter()
    try:
        from app.core.config import get_settings
        from app.tools.miniorange_tool import _list_plugins_sync

        s = get_settings()
        if not s.miniorange_data_dir:
            return ToolResult(
                ok=False,
                name="list_miniorange_plugins",
                summary="MINIORANGE_DATA_DIR not configured",
                error="config_error",
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )

        loop = asyncio.get_running_loop()
        plugins: list[str] = await loop.run_in_executor(None, _list_plugins_sync)
        return ToolResult(
            ok=True,
            name="list_miniorange_plugins",
            summary=f"count={len(plugins)} plugins",
            data={"plugins": plugins, "count": len(plugins)},
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )
    except Exception as exc:
        return ToolResult(
            ok=False,
            name="list_miniorange_plugins",
            summary=str(exc)[:500],
            error="miniorange_error",
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )


async def tool_get_miniorange_plugin(service: str, state: ScanState) -> ToolResult:
    t0 = time.perf_counter()
    try:
        from app.core.config import get_settings
        from app.tools.miniorange_tool import _get_guide_sync

        s = get_settings()
        if not s.miniorange_data_dir:
            return ToolResult(
                ok=False,
                name="get_miniorange_plugin",
                summary="MINIORANGE_DATA_DIR not configured",
                error="config_error",
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )

        loop = asyncio.get_running_loop()
        guide = await loop.run_in_executor(None, _get_guide_sync, service)
        if not guide:
            return ToolResult(
                ok=False,
                name="get_miniorange_plugin",
                summary=f"No guide found for '{service}'",
                error="not_found",
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )

        return ToolResult(
            ok=True,
            name="get_miniorange_plugin",
            summary=f"service={guide.get('service')} auth_type={guide.get('auth_type')}",
            data={
                "service": guide.get("service"),
                "auth_type": guide.get("auth_type"),
                "requires": guide.get("requires", []),
                "description": guide.get("description", ""),
                "setup_steps": guide.get("setup_steps", []),
                "env_template": guide.get("env_template", {}),
            },
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )
    except Exception as exc:
        return ToolResult(
            ok=False,
            name="get_miniorange_plugin",
            summary=str(exc)[:500],
            error="miniorange_error",
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )

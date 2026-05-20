"""FastAPI entrypoint for SentinelGuard."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, analytics, catalog, chat, events, gateway_health, inspect, keys, policies, review
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import init_db
from app.llm.vllm_probe import probe_vllm_tooling


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log = get_logger("sentinelguard")
    s = get_settings()
    log.info("starting", version="0.2.0", mode="pipeline")

    # Shared Redis client for STM, high-impact gate, and pipeline events
    app.state.redis = aioredis.from_url(s.redis_url, decode_responses=True)

    try:
        await asyncio.wait_for(probe_vllm_tooling(), timeout=20.0)
    except TimeoutError:
        log.warning("vllm_probe_timeout")
    except Exception as e:  # noqa: BLE001
        log.warning("vllm_probe_error", error=str(e))
    try:
        await asyncio.wait_for(init_db(), timeout=15.0)
    except TimeoutError:
        log.warning("db_init_timeout")
    yield

    await app.state.redis.aclose()
    log.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="SentinelGuard",
        version="0.2.0",
        description="AI Security Gateway — 14-Stage Sequential Pipeline",
        lifespan=lifespan,
    )

    origins = (
        ["*"]
        if settings.cors_origins.strip() == "*"
        else [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat.router, prefix="/v1", tags=["chat"])
    app.include_router(events.router, prefix="/api", tags=["events"])
    app.include_router(review.router, prefix="/api/review", tags=["review"])
    app.include_router(policies.router, prefix="/api/policies", tags=["policies"])
    app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
    app.include_router(inspect.router, prefix="/api/inspect", tags=["inspect"])
    app.include_router(gateway_health.router, prefix="/api/system/health", tags=["system"])
    app.include_router(keys.router, prefix="/api/keys", tags=["keys"])
    app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
    app.include_router(catalog.router, prefix="/api/catalog", tags=["catalog"])

    # 14-stage pipeline endpoint + session lifecycle
    from app.api.pipeline_chat import router as pipeline_router
    from app.api.session import router as session_router
    app.include_router(pipeline_router, prefix="/api/v2", tags=["pipeline"])
    app.include_router(session_router, prefix="/api/v2", tags=["pipeline"])

    @app.get("/", tags=["health"])
    async def root():
        return {
            "name": "SentinelGuard",
            "version": "0.2.0",
            "status": "ok",
            "docs": "/docs",
        }

    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok"}

    return app


app = create_app()

"""FastAPI entrypoint for SentinelGuard."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import analytics, chat, events, policies, review
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import init_db
from app.llm.vllm_probe import probe_vllm_tooling


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log = get_logger("sentinelguard")
    log.info("starting", version="0.1.0")
    try:
        await probe_vllm_tooling()
    except Exception as e:  # noqa: BLE001
        log.warning("vllm_probe_error", error=str(e))
    await init_db()
    yield
    log.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="SentinelGuard",
        version="0.1.0",
        description="Agentic AI Security Gateway",
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

    @app.get("/", tags=["health"])
    async def root():
        return {
            "name": "SentinelGuard",
            "version": "0.1.0",
            "status": "ok",
            "docs": "/docs",
        }

    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok"}

    return app


app = create_app()

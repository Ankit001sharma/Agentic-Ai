"""Async SQLAlchemy session + engine + init."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import Base

log = get_logger("db")

_settings = get_settings()
engine = create_async_engine(_settings.database_url, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """Create extensions + tables on startup. For MVP we use create_all (no Alembic run-on-boot).

    Alembic migrations are also generated for production use under backend/alembic.
    """
    try:
        async with engine.begin() as conn:
            # Create pgvector extension if missing (idempotent, no-op for sqlite test runs)
            try:
                await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
            except Exception as e:  # noqa: BLE001
                log.warning("pgvector_extension_skip", error=str(e))
            await conn.run_sync(Base.metadata.create_all)
        log.info("db_initialized")
    except Exception as e:  # noqa: BLE001
        # Allow app to boot in offline / dev mode even if DB is down for the moment.
        log.warning("db_init_failed", error=str(e))


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session

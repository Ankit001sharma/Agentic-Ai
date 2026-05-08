"""Structured logging via structlog.

By default, logs use the human-readable colored console renderer when stdout
is a TTY (i.e. you're running uvicorn locally and can see them). When piped
or redirected (containers, log aggregators), JSON is used.

Override with ``LOG_LEVEL`` (DEBUG/INFO/WARNING/...) and
``LOG_FORMAT=console|json`` env vars.
"""

from __future__ import annotations

import logging
import os
import sys

import structlog


def _resolve_format() -> str:
    fmt = (os.getenv("LOG_FORMAT") or "").strip().lower()
    if fmt in {"json", "console"}:
        return fmt
    return "console" if sys.stdout.isatty() else "json"


def configure_logging(level: str | None = None) -> None:
    lvl_name = (level or os.getenv("LOG_LEVEL") or "INFO").upper()
    lvl = getattr(logging, lvl_name, logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=lvl,
    )

    fmt = _resolve_format()
    renderer = (
        structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty(), pad_event=28)
        if fmt == "console"
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(lvl),
        cache_logger_on_first_use=True,
    )

    # Quiet very chatty third-party loggers unless DEBUG is requested
    if lvl > logging.DEBUG:
        for noisy in ("httpx", "httpcore", "litellm", "LiteLLM", "openai"):
            logging.getLogger(noisy).setLevel(max(lvl, logging.WARNING))


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)

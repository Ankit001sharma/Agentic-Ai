"""OpenTelemetry — optional; no-op if package missing."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from app.core.logging import get_logger

log = get_logger("otel")


@contextmanager
def span(_name: str, _attrs: dict[str, Any] | None = None) -> Iterator[None]:
    try:
        from opentelemetry import trace  # type: ignore[import-not-found]  # noqa: PLC0415

        tracer = trace.get_tracer("sentinelguard")
        with tracer.start_as_current_span(_name) as s:
            if _attrs and s is not None:
                for k, v in _attrs.items():
                    s.set_attribute(k, v)
            yield
    except Exception:  # noqa: BLE001
        yield


def init_otel() -> None:
    try:
        from opentelemetry import trace  # type: ignore[import-not-found]  # noqa: PLC0415
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import-not-found]  # noqa: PLC0415

        if not trace.get_tracer_provider():  # type: ignore[truthy-function]
            return
    except Exception:  # noqa: BLE001
        log.info("otel_not_configured")

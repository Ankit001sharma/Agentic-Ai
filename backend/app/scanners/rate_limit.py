"""RateLimitAbuseScanner — detects request flooding and burst abuse via Redis.

Tracks per-user request rates in two sliding windows:
  - 1-minute  : ≥ 30 requests → SPAM finding (severity scales with excess)
  - 10-second : ≥  8 requests → SPAM finding (burst attack signal)

Requires redis_client in the scan context (injected by Stage 2). Silently
passes when redis_client is absent or the user is anonymous.
"""

from __future__ import annotations

from app.schemas.sentinel import Finding

from .base import ScannerResult

_MIN_WINDOW = 60    # seconds
_BURST_WINDOW = 10  # seconds
_MAX_PER_MIN = 30
_MAX_BURST = 8


class RateLimitAbuseScanner:
    name = "rate_limit"

    async def scan(self, text: str, **ctx) -> ScannerResult:
        redis = ctx.get("redis_client")
        user_id = ctx.get("user_id", "anonymous")

        if redis is None or user_id == "anonymous":
            return ScannerResult()

        minute_key = f"ratelimit:1m:{user_id}"
        burst_key = f"ratelimit:10s:{user_id}"

        try:
            minute_count = int(await redis.incr(minute_key))
            if minute_count == 1:
                await redis.expire(minute_key, _MIN_WINDOW)

            burst_count = int(await redis.incr(burst_key))
            if burst_count == 1:
                await redis.expire(burst_key, _BURST_WINDOW)
        except Exception:  # noqa: BLE001
            return ScannerResult()

        findings: list[Finding] = []
        max_sev = 0.0

        if minute_count > _MAX_PER_MIN:
            sev = min(1.0, 0.7 + (minute_count - _MAX_PER_MIN) * 0.01)
            max_sev = max(max_sev, sev)
            findings.append(
                Finding(
                    category="SPAM",
                    scanner=self.name,
                    severity=sev,
                    evidence=f"{minute_count} requests in 60s (max={_MAX_PER_MIN})",
                    metadata={"type": "rate_limit", "window_sec": 60, "count": minute_count},
                )
            )

        if burst_count > _MAX_BURST:
            sev = min(1.0, 0.8 + (burst_count - _MAX_BURST) * 0.02)
            max_sev = max(max_sev, sev)
            findings.append(
                Finding(
                    category="SPAM",
                    scanner=self.name,
                    severity=sev,
                    evidence=f"{burst_count} requests in 10s (max={_MAX_BURST})",
                    metadata={"type": "burst", "window_sec": 10, "count": burst_count},
                )
            )

        return ScannerResult(findings=findings, score=max_sev)

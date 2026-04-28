"""Pytest configuration. Forces SQLite in-memory DB so tests run hermetically."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Use a file-based sqlite so async sessions can share state across awaits.
os.environ.setdefault(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{ROOT.as_posix()}/.cache/test.db",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("OPA_URL", "http://localhost:18181")  # unreachable -> graceful fallback
os.environ.setdefault("SENTINEL_API_KEY", "test-key")
os.environ.setdefault("OPENAI_API_KEY", "")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

# Ensure cache dir exists
(ROOT / ".cache").mkdir(exist_ok=True)

"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-22
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """For MVP, schema is created via SQLAlchemy `create_all` on app startup
    (see app/db/session.py).  This placeholder migration documents the baseline
    so production deploys can switch to real Alembic flow later.
    """
    pass


def downgrade() -> None:
    pass

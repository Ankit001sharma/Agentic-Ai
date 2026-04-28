"""agent traces table (also created via SQLAlchemy create_all)

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Tables are created on boot via ``Base.metadata.create_all`` — migration documents rollout."""
    pass


def downgrade() -> None:
    pass

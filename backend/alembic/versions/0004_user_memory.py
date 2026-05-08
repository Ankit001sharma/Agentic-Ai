"""Long-term user memory table promoted from STM on session end.

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_memory",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False, index=True),
        sa.Column("conv_id", sa.String(64), nullable=False, index=True),
        sa.Column("last_intent", sa.String(128), nullable=True),
        sa.Column("entities", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("tool_executions", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("turn_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("user_memory")

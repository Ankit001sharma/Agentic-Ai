"""Pipeline v2 tables: audit_log, user_risk, scan_findings

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("request_id", sa.String(64), nullable=False, index=True),
        sa.Column("user_id", sa.String(128), nullable=False, index=True),
        sa.Column("conv_id", sa.String(64), nullable=True),
        sa.Column("verdict", sa.String(16), nullable=False),
        sa.Column("risk", sa.Integer(), nullable=False, default=0),
        sa.Column("tool_id", sa.String(64), nullable=True),
        sa.Column("tool_executed", sa.Boolean(), nullable=False, default=False),
        sa.Column("simulated", sa.Boolean(), nullable=False, default=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False, default=0),
        sa.Column("findings_json", sa.Text(), nullable=True),
        sa.Column("tool_args_json", sa.Text(), nullable=True),
        sa.Column("tool_result_json", sa.Text(), nullable=True),
        sa.Column("pipeline_error_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    op.create_table(
        "user_risk",
        sa.Column("user_id", sa.String(128), primary_key=True),
        sa.Column("risk_score", sa.Float(), nullable=False, default=0.0),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "scan_findings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("request_id", sa.String(64), nullable=False, index=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("severity", sa.Float(), nullable=False),
        sa.Column("scanner", sa.String(64), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, default="input"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_scan_findings_user_category", "scan_findings", ["user_id", "category"])


def downgrade() -> None:
    op.drop_table("scan_findings")
    op.drop_table("user_risk")
    op.drop_table("audit_log")

"""Add ops.command table for durable commands

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-26

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "command",
        sa.Column("command_id", sa.String(36), primary_key=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("actor_display_name", sa.String(255), nullable=False),
        sa.Column(
            "book_id", sa.String(36), sa.ForeignKey("core.portfolio_book.book_id"), nullable=True
        ),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("expected_version", sa.Integer, nullable=True),
        sa.Column("payload_json", sa.Text, nullable=False),
        sa.Column("result_reference", sa.String(255), nullable=True),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("failure_message", sa.Text, nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        schema="ops",
    )
    op.create_index("ix_command_status", "command", ["status"], schema="ops")
    op.create_index(
        "ix_command_idempotency",
        "command",
        ["actor_id", "type", "idempotency_key"],
        schema="ops",
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("command", schema="ops")

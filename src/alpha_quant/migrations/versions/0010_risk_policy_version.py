"""Create core.risk_policy_version table

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-30

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "risk_policy_version",
        sa.Column("version_label", sa.String(64), primary_key=True),
        sa.Column("policy_json", sa.Text, nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        schema="core",
    )


def downgrade() -> None:
    op.drop_table("risk_policy_version", schema="core")

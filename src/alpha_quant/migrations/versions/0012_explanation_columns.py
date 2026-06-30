"""Add scope, scope_id, snapshot_id, input_fingerprint, stale to advice_artifact

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-30

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "advice_artifact",
        sa.Column("scope", sa.String(32), nullable=False, server_default="scorecard_overall"),
        schema="run",
    )
    op.add_column(
        "advice_artifact",
        sa.Column("scope_id", sa.String(64), nullable=False, server_default=""),
        schema="run",
    )
    op.add_column(
        "advice_artifact",
        sa.Column("snapshot_id", sa.String(64), nullable=True),
        schema="run",
    )
    op.add_column(
        "advice_artifact",
        sa.Column("input_fingerprint", sa.String(64), nullable=True),
        schema="run",
    )
    op.add_column(
        "advice_artifact",
        sa.Column("stale", sa.Boolean, nullable=False, server_default=sa.text("false")),
        schema="run",
    )


def downgrade() -> None:
    op.drop_column("advice_artifact", "stale", schema="run")
    op.drop_column("advice_artifact", "input_fingerprint", schema="run")
    op.drop_column("advice_artifact", "snapshot_id", schema="run")
    op.drop_column("advice_artifact", "scope_id", schema="run")
    op.drop_column("advice_artifact", "scope", schema="run")

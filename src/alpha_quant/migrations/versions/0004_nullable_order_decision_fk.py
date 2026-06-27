"""Make paper_order.decision_run_id nullable (orders can exist without a run)

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-27

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
    op.alter_column(
        "paper_order",
        "decision_run_id",
        existing_type=sa.String(36),
        nullable=True,
        schema="trade",
    )


def downgrade() -> None:
    op.alter_column(
        "paper_order",
        "decision_run_id",
        existing_type=sa.String(36),
        nullable=False,
        schema="trade",
    )

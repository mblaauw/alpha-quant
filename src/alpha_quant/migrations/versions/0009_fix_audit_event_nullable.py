"""Fix audit_event.decision_run_id to nullable (ORM-defined as fk_opt but migration had nullable=False)

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-29

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "audit_event",
        "decision_run_id",
        existing_type=sa.String(36),
        nullable=True,
        schema="audit",
    )


def downgrade() -> None:
    # First clean up any rows that have NULL before making it NOT NULL again
    op.execute("DELETE FROM audit.audit_event WHERE decision_run_id IS NULL")
    op.alter_column(
        "audit_event",
        "decision_run_id",
        existing_type=sa.String(36),
        nullable=False,
        schema="audit",
    )

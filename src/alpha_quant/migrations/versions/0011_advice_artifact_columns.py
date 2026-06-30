"""Add confidence_label, what_changed_json, override_guidance_json to advice_artifact

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-30

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "advice_artifact",
        sa.Column("confidence_label", sa.String(20), nullable=True, server_default="medium"),
        schema="run",
    )
    op.add_column(
        "advice_artifact",
        sa.Column("what_changed_json", sa.Text, nullable=False, server_default="[]"),
        schema="run",
    )
    op.add_column(
        "advice_artifact",
        sa.Column("override_guidance_json", sa.Text, nullable=False, server_default="[]"),
        schema="run",
    )


def downgrade() -> None:
    op.drop_column("advice_artifact", "confidence_label", schema="run")
    op.drop_column("advice_artifact", "what_changed_json", schema="run")
    op.drop_column("advice_artifact", "override_guidance_json", schema="run")

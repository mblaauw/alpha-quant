"""Add missing advice_artifact columns for explanation persistence

Adds interpretation, key_evidence_json, key_caveats_json, data_quality_notes,
decision_context, educational_context, what_could_change_json to store all
AdviceRecommendation fields.

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-30

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "advice_artifact",
        sa.Column("interpretation", sa.Text, nullable=False, server_default=""),
        schema="run",
    )
    op.add_column(
        "advice_artifact",
        sa.Column("key_evidence_json", sa.Text, nullable=False, server_default="[]"),
        schema="run",
    )
    op.add_column(
        "advice_artifact",
        sa.Column("key_caveats_json", sa.Text, nullable=False, server_default="[]"),
        schema="run",
    )
    op.add_column(
        "advice_artifact",
        sa.Column("data_quality_notes", sa.Text, nullable=False, server_default=""),
        schema="run",
    )
    op.add_column(
        "advice_artifact",
        sa.Column("decision_context", sa.Text, nullable=False, server_default=""),
        schema="run",
    )
    op.add_column(
        "advice_artifact",
        sa.Column("educational_context", sa.Text, nullable=False, server_default=""),
        schema="run",
    )
    op.add_column(
        "advice_artifact",
        sa.Column("what_could_change_json", sa.Text, nullable=False, server_default="[]"),
        schema="run",
    )


def downgrade() -> None:
    op.drop_column("advice_artifact", "what_could_change_json", schema="run")
    op.drop_column("advice_artifact", "educational_context", schema="run")
    op.drop_column("advice_artifact", "decision_context", schema="run")
    op.drop_column("advice_artifact", "data_quality_notes", schema="run")
    op.drop_column("advice_artifact", "key_caveats_json", schema="run")
    op.drop_column("advice_artifact", "key_evidence_json", schema="run")
    op.drop_column("advice_artifact", "interpretation", schema="run")

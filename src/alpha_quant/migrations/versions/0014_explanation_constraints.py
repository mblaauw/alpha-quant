"""Add CHECK constraints on advice_artifact.explanation columns

Adds constraints for scope (must match ExplanationScope values) and
confidence_label (must be low/medium/high).

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-30

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_advice_scope",
        "advice_artifact",
        "scope IN ('scorecard_stage', 'scorecard_overall', 'risk_category', 'risk_overall', 'final_output')",
        schema="run",
    )
    op.create_check_constraint(
        "ck_advice_confidence_label",
        "advice_artifact",
        "confidence_label IN ('low', 'medium', 'high')",
        schema="run",
    )


def downgrade() -> None:
    op.drop_constraint("ck_advice_scope", "advice_artifact", schema="run")
    op.drop_constraint("ck_advice_confidence_label", "advice_artifact", schema="run")

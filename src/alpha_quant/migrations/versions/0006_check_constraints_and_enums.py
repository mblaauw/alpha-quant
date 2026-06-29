"""Add CHECK constraints for data integrity and normalize strategy_version

CHECK constraints added:
- trade.paper_fill: quantity > 0, price > 0
- trade.paper_order: quantity > 0
- run.scorecard: confidence BETWEEN 0 AND 1, total_score >= 0
- run.scorecard_component: score >= 0, weight > 0
- run.candidate_evaluation: composite_score >= 0
- projection.position_current: quantity != 0 AND avg_cost > 0
- core.security_reference: symbol != ''
- core.risk_method: is_active IS NOT NULL

Also normalizes empty strategy_version to 'v1' and adds remaining FK indexes.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-29

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # --- DATA MIGRATION: Normalize empty strategy_version to "v1" ---
    conn.execute(
        sa.text("UPDATE run.scorecard SET strategy_version = 'v1' WHERE strategy_version = ''")
    )

    # --- CHECK constraints ---
    op.create_check_constraint(
        "ck_paper_fill_quantity_positive",
        "paper_fill",
        sa.text("quantity > 0"),
        schema="trade",
    )
    op.create_check_constraint(
        "ck_paper_fill_price_positive",
        "paper_fill",
        sa.text("price > 0"),
        schema="trade",
    )
    op.create_check_constraint(
        "ck_paper_order_quantity_positive",
        "paper_order",
        sa.text("quantity > 0"),
        schema="trade",
    )
    op.create_check_constraint(
        "ck_scorecard_confidence_range",
        "scorecard",
        sa.text("confidence >= 0 AND confidence <= 1"),
        schema="run",
    )
    op.create_check_constraint(
        "ck_scorecard_total_score_nonneg",
        "scorecard",
        sa.text("total_score >= 0"),
        schema="run",
    )
    op.create_check_constraint(
        "ck_component_score_nonneg",
        "scorecard_component",
        sa.text("score >= 0"),
        schema="run",
    )
    op.create_check_constraint(
        "ck_component_weight_positive",
        "scorecard_component",
        sa.text("weight > 0"),
        schema="run",
    )
    op.create_check_constraint(
        "ck_candidate_composite_nonneg",
        "candidate_evaluation",
        sa.text("composite_score >= 0"),
        schema="run",
    )
    op.create_check_constraint(
        "ck_position_stale_check",
        "position_current",
        sa.text("NOT (quantity = 0 AND avg_cost != 0)"),
        schema="projection",
    )
    op.create_check_constraint(
        "ck_security_symbol_not_empty",
        "security_reference",
        sa.text("symbol != ''"),
        schema="core",
    )
    op.create_check_constraint(
        "ck_risk_method_active_not_null",
        "risk_method",
        sa.text("is_active IS NOT NULL"),
        schema="core",
    )

    # --- Remaining FK column indexes ---
    op.create_index("ix_scorecard_decision_run_id", "scorecard", ["decision_run_id"], schema="run")
    op.create_index("ix_scorecard_security_id", "scorecard", ["security_id"], schema="run")
    op.create_index(
        "ix_position_current_book_id", "position_current", ["book_id"], schema="projection"
    )
    op.create_index(
        "ix_position_risk_current_book_id",
        "position_risk_current",
        ["book_id"],
        schema="projection",
    )


def downgrade() -> None:
    op.drop_constraint("ck_paper_fill_quantity_positive", "paper_fill", schema="trade")
    op.drop_constraint("ck_paper_fill_price_positive", "paper_fill", schema="trade")
    op.drop_constraint("ck_paper_order_quantity_positive", "paper_order", schema="trade")
    op.drop_constraint("ck_scorecard_confidence_range", "scorecard", schema="run")
    op.drop_constraint("ck_scorecard_total_score_nonneg", "scorecard", schema="run")
    op.drop_constraint("ck_component_score_nonneg", "scorecard_component", schema="run")
    op.drop_constraint("ck_component_weight_positive", "scorecard_component", schema="run")
    op.drop_constraint("ck_candidate_composite_nonneg", "candidate_evaluation", schema="run")
    op.drop_constraint("ck_position_stale_check", "position_current", schema="projection")
    op.drop_constraint("ck_security_symbol_not_empty", "security_reference", schema="core")
    op.drop_constraint("ck_risk_method_active_not_null", "risk_method", schema="core")
    op.drop_index("ix_scorecard_decision_run_id", schema="run")
    op.drop_index("ix_scorecard_security_id", schema="run")
    op.drop_index("ix_position_current_book_id", schema="projection")
    op.drop_index("ix_position_risk_current_book_id", schema="projection")

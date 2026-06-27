"""Add scorecard, advice, risk, and operator-override tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-27

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
    # core.risk_method
    op.create_table(
        "risk_method",
        sa.Column("risk_method_id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("method_type", sa.String(36), nullable=False),
        sa.Column("default_params_json", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("TRUE")),
        schema="core",
    )

    # run.scorecard
    op.create_table(
        "scorecard",
        sa.Column("scorecard_id", sa.String(36), primary_key=True),
        sa.Column(
            "decision_run_id",
            sa.String(36),
            sa.ForeignKey("run.decision_run.decision_run_id"),
            nullable=False,
        ),  # fmt: skip
        sa.Column(
            "portfolio_book_id",
            sa.String(36),
            sa.ForeignKey("core.portfolio_book.book_id"),
            nullable=False,
        ),  # fmt: skip
        sa.Column("symbol", sa.String(36), nullable=False),
        sa.Column(
            "security_id",
            sa.String(36),
            sa.ForeignKey("core.security_reference.security_id"),
            nullable=False,
        ),  # fmt: skip
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot_id", sa.String(64), nullable=True),
        sa.Column("facts_hash", sa.String(64), nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("strategy_version", sa.String(64), nullable=False),
        sa.Column("recommendation", sa.String(24), nullable=False),
        sa.Column("confidence", sa.Numeric(6, 4), nullable=False),
        sa.Column("total_score", sa.Numeric(8, 4), nullable=False),
        sa.Column("data_quality", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="run",
    )

    # run.scorecard_component
    op.create_table(
        "scorecard_component",
        sa.Column("component_id", sa.String(36), primary_key=True),
        sa.Column(
            "scorecard_id",
            sa.String(36),
            sa.ForeignKey("run.scorecard.scorecard_id"),
            nullable=False,
        ),  # fmt: skip
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("score", sa.Numeric(8, 4), nullable=False),
        sa.Column("state", sa.String(10), nullable=False),
        sa.Column("weight", sa.Numeric(8, 4), nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("details_json", sa.Text, nullable=False),
        schema="run",
    )

    # run.advice_artifact
    op.create_table(
        "advice_artifact",
        sa.Column("advice_id", sa.String(36), primary_key=True),
        sa.Column(
            "scorecard_id",
            sa.String(36),
            sa.ForeignKey("run.scorecard.scorecard_id"),
            nullable=False,
        ),  # fmt: skip
        sa.Column("llm_provider", sa.String(64), nullable=True),
        sa.Column("llm_model", sa.String(64), nullable=True),
        sa.Column("prompt_version", sa.String(64), nullable=True),
        sa.Column("input_hash", sa.String(64), nullable=True),
        sa.Column("output_hash", sa.String(64), nullable=True),
        sa.Column("validation_status", sa.String(20), nullable=True),
        sa.Column("recommendation", sa.String(24), nullable=False),
        sa.Column("headline", sa.Text, nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("rationale_json", sa.Text, nullable=False),
        sa.Column("risks_json", sa.Text, nullable=False),
        sa.Column(
            "deterministic_differs", sa.Boolean, nullable=False, server_default=sa.text("FALSE")
        ),  # fmt: skip
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="run",
    )

    # audit.operator_override
    op.create_table(
        "operator_override",
        sa.Column("override_id", sa.String(36), primary_key=True),
        sa.Column(
            "scorecard_id",
            sa.String(36),
            sa.ForeignKey("run.scorecard.scorecard_id"),
            nullable=False,
        ),  # fmt: skip
        sa.Column(
            "command_id", sa.String(36), sa.ForeignKey("ops.command.command_id"), nullable=False
        ),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("original_recommendation", sa.String(24), nullable=False),
        sa.Column("original_confidence", sa.Numeric(6, 4), nullable=False),
        sa.Column("override_action", sa.String(10), nullable=False),
        sa.Column("modified_recommendation", sa.String(24), nullable=True),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="audit",
    )

    # projection.position_risk_current
    op.create_table(
        "position_risk_current",
        sa.Column(
            "book_id", sa.String(36), sa.ForeignKey("core.portfolio_book.book_id"), primary_key=True
        ),  # fmt: skip
        sa.Column(
            "security_id",
            sa.String(36),
            sa.ForeignKey("core.security_reference.security_id"),
            primary_key=True,
        ),  # fmt: skip
        sa.Column(
            "risk_method_id",
            sa.String(36),
            sa.ForeignKey("core.risk_method.risk_method_id"),
            nullable=True,
        ),  # fmt: skip
        sa.Column("stop_price", sa.Numeric(28, 10), nullable=True),
        sa.Column("trail_price", sa.Numeric(28, 10), nullable=True),
        sa.Column("trail_activation_pct", sa.Numeric(8, 4), nullable=True),
        sa.Column("time_stop_date", sa.Date, nullable=True),
        sa.Column("auto_trail_enabled", sa.Boolean, nullable=False, server_default=sa.text("TRUE")),
        sa.Column("last_adjusted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_adjustment_reason", sa.Text, nullable=True),
        schema="projection",
    )


def downgrade() -> None:
    op.drop_table("position_risk_current", schema="projection")
    op.drop_table("operator_override", schema="audit")
    op.drop_table("advice_artifact", schema="run")
    op.drop_table("scorecard_component", schema="run")
    op.drop_table("scorecard", schema="run")
    op.drop_table("risk_method", schema="core")

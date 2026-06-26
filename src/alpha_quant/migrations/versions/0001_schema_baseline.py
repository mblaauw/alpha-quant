"""Create schema baseline — all schemas and tables

Revision ID: 0001
Revises:
Create Date: 2026-06-26

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS core")
    op.execute("CREATE SCHEMA IF NOT EXISTS run")
    op.execute("CREATE SCHEMA IF NOT EXISTS trade")
    op.execute("CREATE SCHEMA IF NOT EXISTS projection")
    op.execute("CREATE SCHEMA IF NOT EXISTS audit")
    op.execute("CREATE SCHEMA IF NOT EXISTS ops")

    # --- core ---
    op.create_table(
        "strategy",
        sa.Column("strategy_id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="core",
    )
    op.create_table(
        "strategy_version",
        sa.Column("strategy_version_id", sa.String(36), primary_key=True),
        sa.Column(
            "strategy_id", sa.String(36), sa.ForeignKey("core.strategy.strategy_id"), nullable=False
        ),
        sa.Column("version_label", sa.String(64), nullable=False),
        sa.Column("config_json", sa.Text, nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="core",
    )
    op.create_table(
        "portfolio_book",
        sa.Column("book_id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="core",
    )
    op.create_table(
        "security_reference",
        sa.Column("security_id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(36), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("sector", sa.String(64), nullable=True),
        schema="core",
    )
    op.create_table(
        "execution_profile",
        sa.Column("profile_id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("slippage_bps", sa.Integer, nullable=False),
        sa.Column("spread_model", sa.String(64), nullable=False),
        schema="core",
    )

    # --- run ---
    op.create_table(
        "decision_run",
        sa.Column("decision_run_id", sa.String(36), primary_key=True),
        sa.Column("run_key", sa.String(255), unique=True, nullable=False),
        sa.Column("run_kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "strategy_version_id",
            sa.String(36),
            sa.ForeignKey("core.strategy_version.strategy_version_id"),
            nullable=False,
        ),
        sa.Column(
            "portfolio_book_id",
            sa.String(36),
            sa.ForeignKey("core.portfolio_book.book_id"),
            nullable=False,
        ),
        sa.Column("decision_as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("execution_as_of", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_snapshot_id", sa.String(64), nullable=False),
        sa.Column("alpha_lake_api_version", sa.String(64), nullable=False),
        sa.Column("alpha_lake_contract_version", sa.String(64), nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_hash", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text, nullable=True),
        schema="run",
    )
    op.create_table(
        "alpha_lake_manifest",
        sa.Column("manifest_id", sa.String(36), primary_key=True),
        sa.Column(
            "decision_run_id",
            sa.String(36),
            sa.ForeignKey("run.decision_run.decision_run_id"),
            nullable=False,
        ),
        sa.Column("request_body", sa.Text, nullable=False),
        sa.Column("response_body", sa.Text, nullable=False),
        sa.Column("snapshot_id", sa.String(64), nullable=False),
        sa.Column("contract_version", sa.String(64), nullable=False),
        sa.Column("api_version", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="run",
    )
    op.create_table(
        "candidate_evaluation",
        sa.Column("candidate_id", sa.String(36), primary_key=True),
        sa.Column(
            "decision_run_id",
            sa.String(36),
            sa.ForeignKey("run.decision_run.decision_run_id"),
            nullable=False,
        ),
        sa.Column(
            "portfolio_book_id",
            sa.String(36),
            sa.ForeignKey("core.portfolio_book.book_id"),
            nullable=False,
        ),
        sa.Column(
            "security_id",
            sa.String(36),
            sa.ForeignKey("core.security_reference.security_id"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(36), nullable=False),
        sa.Column("composite_score", sa.Numeric(28, 10), nullable=False),
        sa.Column("regime", sa.String(64), nullable=False),
        sa.Column("blocked", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("block_reason", sa.Text, nullable=True),
        sa.Column("gate_results", sa.Text, nullable=False),
        schema="run",
    )
    op.create_table(
        "policy_evaluation",
        sa.Column("evaluation_id", sa.String(36), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.String(36),
            sa.ForeignKey("run.candidate_evaluation.candidate_id"),
            nullable=False,
        ),
        sa.Column("policy_name", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("score", sa.Numeric(28, 10), nullable=True),
        sa.Column("passed", sa.Boolean, nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("details_json", sa.Text, nullable=False),
        schema="run",
    )

    # --- trade ---
    op.create_table(
        "paper_order",
        sa.Column("order_id", sa.String(36), primary_key=True),
        sa.Column(
            "decision_run_id",
            sa.String(36),
            sa.ForeignKey("run.decision_run.decision_run_id"),
            nullable=False,
        ),
        sa.Column(
            "portfolio_book_id",
            sa.String(36),
            sa.ForeignKey("core.portfolio_book.book_id"),
            nullable=False,
        ),
        sa.Column(
            "security_id",
            sa.String(36),
            sa.ForeignKey("core.security_reference.security_id"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(36), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("limit_price", sa.Numeric(28, 10), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("filled_quantity", sa.Numeric(28, 10), nullable=True),
        schema="trade",
    )
    op.create_table(
        "paper_fill",
        sa.Column("fill_id", sa.String(36), primary_key=True),
        sa.Column(
            "order_id", sa.String(36), sa.ForeignKey("trade.paper_order.order_id"), nullable=False
        ),
        sa.Column(
            "security_id",
            sa.String(36),
            sa.ForeignKey("core.security_reference.security_id"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(36), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 10), nullable=False),
        sa.Column("price", sa.Numeric(28, 10), nullable=False),
        sa.Column("fill_key", sa.String(255), nullable=False),
        sa.Column("quality", sa.String(20), nullable=False),
        sa.Column("fee", sa.Numeric(28, 10), nullable=False),
        sa.Column("booked_at", sa.DateTime(timezone=True), nullable=True),
        schema="trade",
    )
    op.create_table(
        "cash_ledger_entry",
        sa.Column("entry_id", sa.String(36), primary_key=True),
        sa.Column(
            "portfolio_book_id",
            sa.String(36),
            sa.ForeignKey("core.portfolio_book.book_id"),
            nullable=False,
        ),
        sa.Column(
            "fill_id", sa.String(36), sa.ForeignKey("trade.paper_fill.fill_id"), nullable=True
        ),
        sa.Column("amount", sa.Numeric(28, 10), nullable=False),
        sa.Column("currency", sa.String(36), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("booked_at", sa.DateTime(timezone=True), nullable=True),
        schema="trade",
    )
    op.create_table(
        "corporate_action_booking",
        sa.Column("booking_id", sa.String(36), primary_key=True),
        sa.Column(
            "portfolio_book_id",
            sa.String(36),
            sa.ForeignKey("core.portfolio_book.book_id"),
            nullable=False,
        ),
        sa.Column(
            "security_id",
            sa.String(36),
            sa.ForeignKey("core.security_reference.security_id"),
            nullable=False,
        ),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("ratio", sa.Numeric(28, 10), nullable=True),
        sa.Column("amount", sa.Numeric(28, 10), nullable=True),
        schema="trade",
    )
    op.create_table(
        "portfolio_mark",
        sa.Column("mark_id", sa.String(36), primary_key=True),
        sa.Column(
            "portfolio_book_id",
            sa.String(36),
            sa.ForeignKey("core.portfolio_book.book_id"),
            nullable=False,
        ),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("cash", sa.Numeric(28, 10), nullable=False),
        sa.Column("equity", sa.Numeric(28, 10), nullable=False),
        sa.Column("gross_exposure", sa.Numeric(28, 10), nullable=False),
        sa.Column("regime", sa.String(64), nullable=False),
        sa.Column("mark_as_of", sa.DateTime(timezone=True), nullable=False),
        schema="trade",
    )

    # --- projection ---
    op.create_table(
        "position_current",
        sa.Column(
            "book_id", sa.String(36), sa.ForeignKey("core.portfolio_book.book_id"), primary_key=True
        ),
        sa.Column(
            "security_id",
            sa.String(36),
            sa.ForeignKey("core.security_reference.security_id"),
            primary_key=True,
        ),
        sa.Column("symbol", sa.String(36), nullable=False),
        sa.Column("quantity", sa.Numeric(28, 10), nullable=False),
        sa.Column("avg_cost", sa.Numeric(28, 10), nullable=False),
        sa.Column("current_price", sa.Numeric(28, 10), nullable=True),
        sa.Column("market_value", sa.Numeric(28, 10), nullable=True),
        sa.Column("unrealized_pl", sa.Numeric(28, 10), nullable=True),
        sa.Column("stop_price", sa.Numeric(28, 10), nullable=True),
        schema="projection",
    )
    op.create_table(
        "portfolio_current",
        sa.Column(
            "book_id", sa.String(36), sa.ForeignKey("core.portfolio_book.book_id"), primary_key=True
        ),
        sa.Column("cash", sa.Numeric(28, 10), nullable=False),
        sa.Column("equity", sa.Numeric(28, 10), nullable=False),
        sa.Column("gross_exposure", sa.Numeric(28, 10), nullable=False),
        sa.Column("regime", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema="projection",
    )

    # --- audit ---
    op.create_table(
        "audit_event",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column(
            "decision_run_id",
            sa.String(36),
            sa.ForeignKey("run.decision_run.decision_run_id"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="audit",
    )
    op.create_table(
        "risk_event",
        sa.Column("risk_event_id", sa.String(36), primary_key=True),
        sa.Column(
            "decision_run_id",
            sa.String(36),
            sa.ForeignKey("run.decision_run.decision_run_id"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(36), nullable=False),
        sa.Column("details_json", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="audit",
    )
    op.create_table(
        "halt_transition",
        sa.Column("halt_id", sa.String(36), primary_key=True),
        sa.Column(
            "portfolio_book_id",
            sa.String(36),
            sa.ForeignKey("core.portfolio_book.book_id"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(36), nullable=False),
        sa.Column("details", sa.Text, nullable=False),
        sa.Column("halted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resumed_at", sa.DateTime(timezone=True), nullable=True),
        schema="audit",
    )

    # --- ops ---
    op.create_table(
        "current_halt",
        sa.Column(
            "book_id", sa.String(36), sa.ForeignKey("core.portfolio_book.book_id"), primary_key=True
        ),
        sa.Column("halted", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("reason", sa.String(36), nullable=True),
        sa.Column("details", sa.Text, nullable=True),
        sa.Column("halted_at", sa.DateTime(timezone=True), nullable=True),
        schema="ops",
    )
    op.create_table(
        "run_lock_audit",
        sa.Column("lock_id", sa.String(36), primary_key=True),
        sa.Column("run_key", sa.String(255), nullable=False),
        sa.Column("action", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="ops",
    )


def downgrade() -> None:
    for schema in ("ops", "audit", "projection", "trade", "run", "core"):
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")

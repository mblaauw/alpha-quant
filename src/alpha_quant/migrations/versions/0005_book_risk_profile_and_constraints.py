"""Add core.book_risk_profile table, UNIQUE constraints, and FK indexes

- Data migration: normalize bare-symbol security_ids to canonical UUIDs
- Creates core.book_risk_profile table (was referenced by code but missing)
- Adds UNIQUE constraint on core.security_reference.symbol
- Adds UNIQUE constraint on trade.portfolio_mark(portfolio_book_id, effective_date)
- Adds CHECK constraints on trade.cash_ledger_entry.amount != 0
- Adds FK column indexes for query performance

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-29

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# uuid5(NAMESPACE_DNS, symbol + ".com") deterministic security IDs
_CANONICAL_IDS: dict[str, str] = {
    "MSFT": "9127d8e6-fe73-5e2f-858d-4ddb53b41566",
    "AAPL": "af5e031c-716a-5a0d-8d32-72918f96e458",
    "AMZN": "10bb5cae-1167-5cc8-b6c9-89834d18b1ba",
    "NVDA": "4183e344-2aa8-5ef2-9622-958dba344d85",
    "GOOGL": "6412c282-63ab-58a1-90cd-4da700972f0c",
}


def upgrade() -> None:
    conn = op.get_bind()

    # --- DATA MIGRATION: Normalize bare-symbol security_ids ---
    # Some scorecards and security_reference rows were created with bare
    # symbols ("MSFT") as security_id instead of canonical UUIDs. Fix them
    # before adding the UNIQUE constraint on symbol.
    for bare_sym, canonical_uuid in _CANONICAL_IDS.items():
        conn.execute(
            sa.text("UPDATE run.scorecard SET security_id = :uuid WHERE security_id = :bare"),
            {"uuid": canonical_uuid, "bare": bare_sym},
        )
    for bare_sym in _CANONICAL_IDS:
        conn.execute(
            sa.text("DELETE FROM core.security_reference WHERE security_id = :bare"),
            {"bare": bare_sym},
        )

    # --- DATA MIGRATION: Deduplicate portfolio_mark before UNIQUE constraint ---
    # Keep only the latest mark (by mark_as_of) per (book_id, effective_date).
    conn.execute(
        sa.text(
            "DELETE FROM trade.portfolio_mark WHERE mark_id NOT IN ("
            "SELECT DISTINCT ON (portfolio_book_id, effective_date) mark_id "
            "FROM trade.portfolio_mark "
            "ORDER BY portfolio_book_id, effective_date, mark_as_of DESC"
            ")"
        )
    )

    # --- core.book_risk_profile (P0 — referenced by code but missing) ---
    op.create_table(
        "book_risk_profile",
        sa.Column(
            "book_id", sa.String(36), sa.ForeignKey("core.portfolio_book.book_id"), nullable=False
        ),
        sa.Column("risk_method_id", sa.String(36), nullable=False),
        sa.Column("params_json", sa.Text, nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("book_id"),
        schema="core",
    )

    # --- UNIQUE constraints ---
    op.create_unique_constraint(
        "uq_security_reference_symbol", "security_reference", ["symbol"], schema="core"
    )
    op.create_unique_constraint(
        "uq_portfolio_mark_book_date",
        "portfolio_mark",
        ["portfolio_book_id", "effective_date"],
        schema="trade",
    )

    # --- CHECK constraints ---
    op.create_check_constraint(
        "ck_cash_ledger_amount_nonzero",
        "cash_ledger_entry",
        sa.text("amount != 0"),
        schema="trade",
    )

    # --- FK column indexes for join performance ---
    op.create_index(
        "ix_scorecard_component_scorecard_id", "scorecard_component", ["scorecard_id"], schema="run"
    )
    op.create_index(
        "ix_policy_evaluation_candidate_id", "policy_evaluation", ["candidate_id"], schema="run"
    )
    op.create_index("ix_paper_fill_order_id", "paper_fill", ["order_id"], schema="trade")
    op.create_index(
        "ix_candidate_evaluation_decision_run_id",
        "candidate_evaluation",
        ["decision_run_id"],
        schema="run",
    )
    op.create_index(
        "ix_audit_event_decision_run_id", "audit_event", ["decision_run_id"], schema="audit"
    )
    op.create_index(
        "ix_advice_artifact_scorecard_id", "advice_artifact", ["scorecard_id"], schema="run"
    )
    op.create_index("ix_cash_ledger_fill_id", "cash_ledger_entry", ["fill_id"], schema="trade")
    op.create_index(
        "ix_paper_order_decision_run_id", "paper_order", ["decision_run_id"], schema="trade"
    )


def downgrade() -> None:
    op.drop_table("book_risk_profile", schema="core")
    op.drop_constraint(
        "uq_security_reference_symbol", "security_reference", type_="unique", schema="core"
    )
    op.drop_constraint(
        "uq_portfolio_mark_book_date", "portfolio_mark", type_="unique", schema="trade"
    )
    op.drop_constraint(
        "ck_cash_ledger_amount_nonzero", "cash_ledger_entry", type_="check", schema="trade"
    )
    op.drop_index("ix_scorecard_component_scorecard_id", schema="run")
    op.drop_index("ix_policy_evaluation_candidate_id", schema="run")
    op.drop_index("ix_paper_fill_order_id", schema="trade")
    op.drop_index("ix_candidate_evaluation_decision_run_id", schema="run")
    op.drop_index("ix_audit_event_decision_run_id", schema="audit")
    op.drop_index("ix_advice_artifact_scorecard_id", schema="run")
    op.drop_index("ix_cash_ledger_fill_id", schema="trade")
    op.drop_index("ix_paper_order_decision_run_id", schema="trade")

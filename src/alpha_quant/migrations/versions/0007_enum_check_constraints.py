"""Add DB-level CHECK constraints for all enum columns

Previously all enum-like columns used create_constraint=False, meaning any
string could be stored. This adds CHECK constraints matching the StrEnum
values defined in contracts/operational.py and domain/scorecard.py.

Also adds remaining FK indexes for query performance.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-29

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum_check(name: str, table: str, column: str, values: list[str], schema: str) -> None:
    in_clause = ", ".join(f"'{v}'" for v in values)
    op.create_check_constraint(
        name,
        table,
        sa.text(f"{column} IN ({in_clause})"),
        schema=schema,
    )


def upgrade() -> None:
    # --- SAEnum mapped columns ---
    _enum_check(
        "ck_decision_run_kind", "decision_run", "run_kind", ["daily", "backtest", "replay"], "run"
    )
    _enum_check(
        "ck_decision_run_status",
        "decision_run",
        "status",
        ["reserved", "running", "completed", "failed", "halted"],
        "run",
    )
    _enum_check("ck_paper_order_side", "paper_order", "side", ["buy", "sell"], "trade")
    _enum_check("ck_paper_fill_side", "paper_fill", "side", ["buy", "sell"], "trade")
    _enum_check(
        "ck_paper_order_status",
        "paper_order",
        "status",
        ["pending", "submitted", "partially_filled", "filled", "cancelled"],
        "trade",
    )
    _enum_check(
        "ck_paper_fill_quality",
        "paper_fill",
        "quality",
        ["open", "stop", "gap", "partial"],
        "trade",
    )
    _enum_check(
        "ck_halt_reason",
        "halt_transition",
        "reason",
        ["daily_loss", "drawdown", "staleness", "invariant", "manual"],
        "audit",
    )
    _enum_check(
        "ck_current_halt_reason",
        "current_halt",
        "reason",
        ["daily_loss", "drawdown", "staleness", "invariant", "manual"],
        "ops",
    )

    # --- Plain-string columns with StrEnum semantics ---
    _enum_check(
        "ck_scorecard_recommendation",
        "scorecard",
        "recommendation",
        ["watch", "consider_entry", "hold", "add", "reduce", "exit", "do_nothing"],
        "run",
    )
    _enum_check(
        "ck_scorecard_data_quality", "scorecard", "data_quality", ["pass", "warn", "fail"], "run"
    )
    _enum_check(
        "ck_component_state", "scorecard_component", "state", ["pass", "warn", "fail"], "run"
    )
    _enum_check(
        "ck_command_status",
        "command",
        "status",
        [
            "requested",
            "validated",
            "queued",
            "running",
            "succeeded",
            "failed",
            "cancel_requested",
            "cancelled",
            "rejected",
        ],
        "ops",
    )
    _enum_check(
        "ck_advice_validation_status",
        "advice_artifact",
        "validation_status",
        ["verified", "unverified", "failed"],
        "run",
    )

    # --- Remaining FK indexes ---
    op.create_index(
        "ix_candidate_security_id", "candidate_evaluation", ["security_id"], schema="run"
    )
    op.create_index("ix_paper_order_book_id", "paper_order", ["portfolio_book_id"], schema="trade")
    op.create_index("ix_paper_fill_security_id", "paper_fill", ["security_id"], schema="trade")
    op.create_index(
        "ix_cash_ledger_book_id", "cash_ledger_entry", ["portfolio_book_id"], schema="trade"
    )


def downgrade() -> None:
    _constraints = [
        ("ck_decision_run_kind", "decision_run", "run"),
        ("ck_decision_run_status", "decision_run", "run"),
        ("ck_paper_order_side", "paper_order", "trade"),
        ("ck_paper_fill_side", "paper_fill", "trade"),
        ("ck_paper_order_status", "paper_order", "trade"),
        ("ck_paper_fill_quality", "paper_fill", "trade"),
        ("ck_halt_reason", "halt_transition", "audit"),
        ("ck_current_halt_reason", "current_halt", "ops"),
        ("ck_scorecard_recommendation", "scorecard", "run"),
        ("ck_scorecard_data_quality", "scorecard", "run"),
        ("ck_component_state", "scorecard_component", "run"),
        ("ck_command_status", "command", "ops"),
        ("ck_advice_validation_status", "advice_artifact", "run"),
    ]
    for name, table, schema in _constraints:
        op.drop_constraint(name, table, schema=schema)
    op.drop_index("ix_candidate_security_id", schema="run")
    op.drop_index("ix_paper_order_book_id", schema="trade")
    op.drop_index("ix_paper_fill_security_id", schema="trade")
    op.drop_index("ix_cash_ledger_book_id", schema="trade")

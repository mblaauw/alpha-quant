from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
import sqlalchemy as sa

from alpha_quant.adapters.postgres import create_session
from alpha_quant.adapters.postgres.engine import init_schema
from alpha_quant.adapters.postgres.unit_of_work import OperationalUnitOfWork
from tests.conftest import require_postgres_engine


@pytest.fixture(scope="module")
def engine():
    e = require_postgres_engine()
    init_schema(e)
    yield e
    e.dispose()


@pytest.fixture()
def read_session(engine):
    Session = create_session(engine)  # noqa: N806
    s = Session()
    s.execute(
        sa.text(
            "TRUNCATE TABLE"
            " ops.current_halt, ops.run_lock_audit,"
            " audit.halt_transition, audit.risk_event, audit.audit_event,"
            " projection.portfolio_current, projection.position_current,"
            " trade.portfolio_mark, trade.corporate_action_booking, trade.cash_ledger_entry,"
            " trade.paper_fill, trade.paper_order,"
            " run.policy_evaluation, run.candidate_evaluation, run.alpha_lake_manifest,"
            " run.decision_run, core.strategy_version, core.strategy,"
            " core.portfolio_book, core.security_reference, core.execution_profile"
            " CASCADE"
        )
    )
    s.commit()
    yield s
    s.close()


class TestUnitOfWork:
    def test_enter_exit_commits(self, engine, read_session):
        from sqlalchemy.orm import sessionmaker

        factory = sessionmaker(bind=engine)
        uow = OperationalUnitOfWork(factory)
        bid = str(uuid4())

        with uow as unit:
            unit.session.execute(
                sa.text(
                    "INSERT INTO core.portfolio_book (book_id, name, kind, created_at)"
                    " VALUES (:bid, :n, :k, :now)"
                ),
                {
                    "bid": bid,
                    "n": "uow-test",
                    "k": "paper",
                    "now": datetime.now(UTC),
                },
            )

        row = read_session.execute(
            sa.text("SELECT name FROM core.portfolio_book WHERE book_id = :bid"),
            {"bid": bid},
        ).fetchone()
        assert row is not None
        assert row._mapping["name"] == "uow-test"

    def test_rollback_on_exception(self, engine, read_session):
        from sqlalchemy.orm import sessionmaker

        factory = sessionmaker(bind=engine)
        uow = OperationalUnitOfWork(factory)
        bid = str(uuid4())

        with pytest.raises(RuntimeError), uow as unit:
            unit.session.execute(
                sa.text(
                    "INSERT INTO core.portfolio_book (book_id, name, kind, created_at)"
                    " VALUES (:bid, :n, :k, :now)"
                ),
                {
                    "bid": bid,
                    "n": "should-rollback",
                    "k": "paper",
                    "now": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                },
            )
            raise RuntimeError("force rollback")

        row = read_session.execute(
            sa.text("SELECT name FROM core.portfolio_book WHERE book_id = :bid"),
            {"bid": bid},
        ).fetchone()
        assert row is None, "rollback should have prevented commit"

    def test_store_is_available(self, engine):
        from sqlalchemy.orm import sessionmaker

        factory = sessionmaker(bind=engine)
        uow = OperationalUnitOfWork(factory)

        with uow as unit:
            assert unit.store is not None
            runs = unit.store.list_strategies()
            assert isinstance(runs, list)

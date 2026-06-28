from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from alpha_quant.adapters.postgres import (
    PostgresOperationalStore,
    create_session,
    health_check,
)
from alpha_quant.adapters.postgres.engine import init_schema
from alpha_quant.contracts.operational import (
    CandidateEvaluation,
    DecisionBatch,
    FillBookingCommand,
    FillQuality,
    HaltCommand,
    HaltReason,
    OrderSide,
    PolicyEvaluation,
    PortfolioMark,
    RunKind,
    RunReservation,
    RunStatus,
)
from tests.conftest import require_postgres_engine


@pytest.fixture(scope="module")
def engine():
    e = require_postgres_engine()
    init_schema(e)
    yield e
    e.dispose()


@pytest.fixture()
def session(engine):
    Session = create_session(engine)  # noqa: N806
    s = Session()
    s.execute(
        text(
            "TRUNCATE TABLE"
            " ops.current_halt, ops.run_lock_audit,"
            " audit.halt_transition, audit.risk_event, audit.audit_event,"
            " projection.portfolio_current, projection.position_current,"
            " trade.portfolio_mark, trade.corporate_action_booking, trade.cash_ledger_entry,"
            " trade.paper_fill, trade.paper_order,"
            " run.policy_evaluation, run.candidate_evaluation, run.alpha_lake_manifest, run.decision_run"  # noqa: E501
            " CASCADE"
        )
    )
    s.commit()
    yield s
    s.close()


@pytest.fixture()
def store(session):
    return PostgresOperationalStore(session)


@pytest.fixture()
def book_id(session):
    bid = str(uuid4())
    session.execute(
        text(
            "INSERT INTO core.portfolio_book (book_id, name, kind, created_at) VALUES (:bid, :n, :k, :now)"  # noqa: E501
        ),
        {"bid": bid, "n": "test-book", "k": "backtest", "now": datetime.now(UTC)},
    )
    session.commit()
    return UUID(bid)


@pytest.fixture()
def strategy_id(session):
    sid = str(uuid4())
    svid = str(uuid4())
    now = datetime.now(UTC)
    session.execute(
        text("INSERT INTO core.strategy (strategy_id, name, created_at) VALUES (:sid, :n, :now)"),
        {"sid": sid, "n": "test-strategy", "now": now},
    )
    session.execute(
        text(
            "INSERT INTO core.strategy_version (strategy_version_id, strategy_id, version_label, config_json, config_hash, created_at) VALUES (:svid, :sid, :vl, :cj, :ch, :now)"  # noqa: E501
        ),
        {"svid": svid, "sid": sid, "vl": "v1", "cj": "{}", "ch": "abc", "now": now},
    )
    session.commit()
    return UUID(sid), UUID(svid)


class TestHealthCheck:
    def test_health_returns_healthy(self, engine):
        result = health_check(engine)
        assert result["status"] == "healthy"
        assert result["db"] is True


class TestRunLifecycle:
    def test_reserve_and_complete_run(self, store, session, book_id, strategy_id):
        _, svid = strategy_id
        now = datetime.now(UTC)
        reservation = RunReservation(
            run_key="test-run-001",
            run_kind=RunKind.DAILY,
            strategy_version_id=svid,
            portfolio_book_id=book_id,
            decision_as_of=now,
            resolved_snapshot_id="snap-001",
            alpha_lake_api_version="1.0",
            alpha_lake_contract_version="2.0",
            config_hash="cfg123",
            request_hash="req456",
            response_hash="res789",
        )

        run = store.reserve_run(reservation)
        assert run.run_key == "test-run-001"
        assert run.status == RunStatus.RESERVED
        session.commit()

        store.start_run(run.decision_run_id)
        session.commit()

        fetched = store.get_run_by_key("test-run-001")
        assert fetched is not None
        assert fetched.status == RunStatus.RUNNING

        store.complete_run(run.decision_run_id, "completed")
        session.commit()

        fetched = store.get_run_by_key("test-run-001")
        assert fetched is not None
        assert fetched.status == RunStatus.COMPLETED
        assert fetched.completed_at is not None

    def test_list_runs(self, store, session, book_id):
        runs = store.list_decision_runs(book_id)
        assert isinstance(runs, list)

    def test_get_nonexistent_run(self, store):
        assert store.get_run_by_key("nonexistent") is None


class TestDecisionBatch:
    def test_commit_batch(self, store, session, book_id, strategy_id):
        _, svid = strategy_id
        now = datetime.now(UTC)
        run = store.reserve_run(
            RunReservation(
                run_key="batch-test",
                run_kind=RunKind.DAILY,
                strategy_version_id=svid,
                portfolio_book_id=book_id,
                decision_as_of=now,
                resolved_snapshot_id="snap-001",
                alpha_lake_api_version="1.0",
                alpha_lake_contract_version="2.0",
                config_hash="cfg",
                request_hash="req",
                response_hash="res",
            )
        )
        session.commit()

        sec_id = str(uuid4())
        session.execute(
            text("INSERT INTO core.security_reference (security_id, symbol) VALUES (:sid, :sym)"),
            {"sid": sec_id, "sym": "AAPL"},
        )
        session.commit()

        cand = CandidateEvaluation(
            candidate_id=uuid4(),
            decision_run_id=run.decision_run_id,
            portfolio_book_id=book_id,
            security_id=UUID(sec_id),
            symbol="AAPL",
            composite_score=Decimal("85.5"),
            regime="bull",
            blocked=False,
            gate_results='{"sharpe": 1.5}',
        )
        pe = PolicyEvaluation(
            evaluation_id=uuid4(),
            candidate_id=cand.candidate_id,
            policy_name="sizing",
            policy_version="v2",
            score=Decimal("10.0"),
            passed=True,
            details_json="{}",
        )
        batch = DecisionBatch(
            decision_run_id=run.decision_run_id,
            candidates=[cand],
            policy_evals=[pe],
        )
        store.commit_decision_batch(batch)
        session.commit()

        candidates = store.list_candidates(run.decision_run_id)
        assert len(candidates) == 1
        assert candidates[0].symbol == "AAPL"
        assert candidates[0].composite_score == Decimal("85.5")

        evals = store.list_policy_evals(run.decision_run_id)
        assert len(evals) == 1


class TestFills:
    def test_book_fill_idempotent(self, store, session, book_id, strategy_id):
        _, svid = strategy_id
        now = datetime.now(UTC)
        run = store.reserve_run(
            RunReservation(
                run_key="fill-test",
                run_kind=RunKind.DAILY,
                strategy_version_id=svid,
                portfolio_book_id=book_id,
                decision_as_of=now,
                resolved_snapshot_id="snap",
                alpha_lake_api_version="1.0",
                alpha_lake_contract_version="2.0",
                config_hash="cfg",
                request_hash="req",
                response_hash="res",
            )
        )
        session.commit()

        sec_id = UUID(str(uuid4()))
        session.execute(
            text("INSERT INTO core.security_reference (security_id, symbol) VALUES (:sid, :sym)"),
            {"sid": str(sec_id), "sym": "AAPL"},
        )

        order_id = uuid4()
        session.execute(
            text(
                "INSERT INTO trade.paper_order (order_id, decision_run_id, portfolio_book_id, security_id, symbol, side, quantity, status, idempotency_key) VALUES (:oid, :rid, :pbid, :sid, :sym, :s, :q, :st, :ik)"  # noqa: E501
            ),
            {
                "oid": str(order_id),
                "rid": str(run.decision_run_id),
                "pbid": str(book_id),
                "sid": str(sec_id),
                "sym": "AAPL",
                "s": "buy",
                "q": "100",
                "st": "pending",
                "ik": "ik-001",
            },
        )
        session.commit()

        cmd = FillBookingCommand(
            order_id=order_id,
            decision_run_id=run.decision_run_id,
            portfolio_book_id=book_id,
            security_id=sec_id,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=Decimal("100"),
            price=Decimal("150.00"),
            fill_key="fill-key-001",
            idempotency_key="ik-001",
            quality=FillQuality.OPEN,
        )

        result1 = store.book_fill(cmd)
        session.commit()
        assert result1.already_booked is False
        assert result1.fill_key == "fill-key-001"

        result2 = store.book_fill(cmd)
        session.commit()
        assert result2.already_booked is True


class TestHalts:
    def test_set_and_clear_halt(self, store, session, book_id):
        cmd = HaltCommand(
            portfolio_book_id=book_id,
            reason=HaltReason.DAILY_LOSS,
            details="Hit 2% daily loss limit",
        )
        store.set_halt(cmd)
        session.commit()

        halt = store.current_halt(book_id)
        assert halt is not None
        assert halt.halted is True
        assert halt.reason == HaltReason.DAILY_LOSS

        store.clear_halt(book_id)
        session.commit()

        halt = store.current_halt(book_id)
        assert halt is not None
        assert halt.halted is False

    def test_current_halt_nonexistent(self, store):
        assert store.current_halt(uuid4()) is None


class TestPortfolioMarks:
    def test_save_portfolio_mark(self, store, session, book_id):
        mark = PortfolioMark(
            mark_id=uuid4(),
            portfolio_book_id=book_id,
            effective_date=datetime.now(UTC).date(),
            cash=Decimal("100000"),
            equity=Decimal("150000"),
            gross_exposure=Decimal("50000"),
            regime="bull",
            mark_as_of=datetime.now(UTC),
        )
        store.save_portfolio_mark(mark)
        session.commit()

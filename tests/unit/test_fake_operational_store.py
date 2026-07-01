from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from alpha_quant.adapters.fake.operational_store import FakeOperationalStore
from alpha_quant.adapters.fake.unit_of_work import FakeUnitOfWork
from alpha_quant.contracts.operational import (
    CandidateEvaluation,
    CommandEnvelope,
    CommandStatus,
    DecisionBatch,
    FillBookingCommand,
    FillBookingResult,
    FillQuality,
    HaltCommand,
    HaltReason,
    OrderSide,
    PolicyEvaluation,
    PortfolioBook,
    PortfolioMark,
    RunKind,
    RunReservation,
    RunStatus,
    Strategy,
)
from alpha_quant.domain.scorecard import Recommendation, Scorecard, ScorecardComponent


class TestFakeRunLifecycle:
    def test_reserve_and_complete_run(self) -> None:
        store = FakeOperationalStore()
        book_id = uuid4()
        svid = uuid4()
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

        store.start_run(run.decision_run_id)

        fetched = store.get_run_by_key("test-run-001")
        assert fetched is not None
        assert fetched.status == RunStatus.RUNNING

        store.complete_run(run.decision_run_id, "completed")

        fetched = store.get_run_by_key("test-run-001")
        assert fetched is not None
        assert fetched.status == RunStatus.COMPLETED
        assert fetched.completed_at is not None

    def test_list_runs(self) -> None:
        store = FakeOperationalStore()
        book_id = uuid4()
        runs = store.list_decision_runs(book_id)
        assert isinstance(runs, list)

    def test_get_nonexistent_run(self) -> None:
        store = FakeOperationalStore()
        assert store.get_run_by_key("nonexistent") is None


class TestFakeDecisionBatch:
    def test_commit_batch(self) -> None:
        store = FakeOperationalStore()
        book_id = uuid4()
        svid = uuid4()
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

        cand = CandidateEvaluation(
            candidate_id=uuid4(),
            decision_run_id=run.decision_run_id,
            portfolio_book_id=book_id,
            security_id=uuid4(),
            symbol="TEST_BATCH",
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

        candidates = store.list_candidates(run.decision_run_id)
        assert len(candidates) == 1
        assert candidates[0].symbol == "TEST_BATCH"
        assert candidates[0].composite_score == Decimal("85.5")

        evals = store.list_policy_evals(run.decision_run_id)
        assert len(evals) == 1


class TestFakeFills:
    def test_book_fill_idempotent(self) -> None:
        store = FakeOperationalStore()
        book_id = uuid4()
        svid = uuid4()
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

        sec_id = uuid4()
        order_id = uuid4()

        cmd = FillBookingCommand(
            order_id=order_id,
            decision_run_id=run.decision_run_id,
            portfolio_book_id=book_id,
            security_id=sec_id,
            symbol="TEST_FILL",
            side=OrderSide.BUY,
            quantity=Decimal("100"),
            price=Decimal("150.00"),
            fill_key="fill-key-001",
            idempotency_key="ik-001",
            quality=FillQuality.OPEN,
        )

        result1 = store.book_fill(cmd)
        assert result1.already_booked is False
        assert result1.fill_key == "fill-key-001"

        result2 = store.book_fill(cmd)
        assert result2.already_booked is True

    def test_fill_computes_correct_cash(self) -> None:
        store = FakeOperationalStore()
        book_id = uuid4()
        svid = uuid4()
        now = datetime.now(UTC)
        run = store.reserve_run(
            RunReservation(
                run_key="fill-cash-test",
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

        sec_id = uuid4()
        order_id = uuid4()

        buy_cmd = FillBookingCommand(
            order_id=order_id,
            decision_run_id=run.decision_run_id,
            portfolio_book_id=book_id,
            security_id=sec_id,
            symbol="TEST",
            side=OrderSide.BUY,
            quantity=Decimal("10"),
            price=Decimal("100.00"),
            fill_key="buy-001",
            idempotency_key="ik-001",
        )
        store.book_fill(buy_cmd)

        portfolio = store.load_portfolio(book_id)
        assert portfolio.cash == Decimal("-1000")

        sell_cmd = FillBookingCommand(
            order_id=uuid4(),
            decision_run_id=run.decision_run_id,
            portfolio_book_id=book_id,
            security_id=sec_id,
            symbol="TEST",
            side=OrderSide.SELL,
            quantity=Decimal("5"),
            price=Decimal("110.00"),
            fill_key="sell-001",
            idempotency_key="ik-002",
        )
        store.book_fill(sell_cmd)

        portfolio = store.load_portfolio(book_id)
        assert portfolio.cash == Decimal("-1000") + Decimal("550")


class TestFakeHalts:
    def test_set_and_clear_halt(self) -> None:
        store = FakeOperationalStore()
        book_id = uuid4()
        cmd = HaltCommand(
            portfolio_book_id=book_id,
            reason=HaltReason.DAILY_LOSS,
            details="Hit 2% daily loss limit",
        )
        store.set_halt(cmd)

        halt = store.current_halt(book_id)
        assert halt is not None
        assert halt.halted is True
        assert halt.reason == HaltReason.DAILY_LOSS

        store.clear_halt(book_id)

        halt = store.current_halt(book_id)
        assert halt is not None
        assert halt.halted is False

    def test_current_halt_nonexistent(self) -> None:
        store = FakeOperationalStore()
        assert store.current_halt(uuid4()) is None


class TestFakePortfolioMarks:
    def test_save_portfolio_mark(self) -> None:
        store = FakeOperationalStore()
        book_id = uuid4()
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

    def test_save_portfolio_mark_upsert(self) -> None:
        store = FakeOperationalStore()
        book_id = uuid4()
        today = datetime.now(UTC).date()
        mark1 = PortfolioMark(
            mark_id=uuid4(),
            portfolio_book_id=book_id,
            effective_date=today,
            cash=Decimal("100000"),
            equity=Decimal("150000"),
            gross_exposure=Decimal("50000"),
            regime="bull",
            mark_as_of=datetime.now(UTC),
        )
        mark2 = PortfolioMark(
            mark_id=uuid4(),
            portfolio_book_id=book_id,
            effective_date=today,
            cash=Decimal("200000"),
            equity=Decimal("250000"),
            gross_exposure=Decimal("100000"),
            regime="bear",
            mark_as_of=datetime.now(UTC),
        )
        store.save_portfolio_mark(mark1)
        store.save_portfolio_mark(mark2)


class TestFakeUnitOfWork:
    def test_enter_exit(self) -> None:
        store = FakeOperationalStore()
        uow = FakeUnitOfWork(store)
        with uow as unit:
            assert unit.store is not None
            runs = unit.store.list_strategies()
            assert isinstance(runs, list)

    def test_store_outside_context_raises(self) -> None:
        uow = FakeUnitOfWork()
        try:
            _ = uow.store
            assert False, "Should have raised"
        except RuntimeError:
            pass

    def test_factory_creates_fake(self) -> None:
        from alpha_quant.application.factory import create_unit_of_work

        uow = create_unit_of_work(store_mode="fake")
        assert uow is not None
        with uow as unit:
            assert unit.store is not None


class TestFakeProjections:
    def test_rebuild_projections(self) -> None:
        store = FakeOperationalStore()
        book_id = uuid4()
        sec_id = uuid4()
        svid = uuid4()
        now = datetime.now(UTC)
        run = store.reserve_run(
            RunReservation(
                run_key="proj-test",
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

        buy = FillBookingCommand(
            order_id=uuid4(),
            decision_run_id=run.decision_run_id,
            portfolio_book_id=book_id,
            security_id=sec_id,
            symbol="TEST",
            side=OrderSide.BUY,
            quantity=Decimal("100"),
            price=Decimal("50.00"),
            fill_key="proj-buy",
            idempotency_key="ik-1",
        )
        store.book_fill(buy)

        store.rebuild_projections(book_id)
        positions = store.list_positions(book_id)
        assert len(positions) == 1
        assert positions[0].symbol == "TEST"
        assert positions[0].quantity == Decimal("100")
        assert positions[0].avg_cost == Decimal("50")
        assert positions[0].current_price == Decimal("50")
        assert positions[0].market_value == Decimal("5000")

    def test_rebuild_projections_with_sell_reduces_qty(self) -> None:
        store = FakeOperationalStore()
        book_id = uuid4()
        sec_id = uuid4()
        svid = uuid4()
        now = datetime.now(UTC)
        run = store.reserve_run(
            RunReservation(
                run_key="proj-sell-test",
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

        store.book_fill(
            FillBookingCommand(
                order_id=uuid4(),
                decision_run_id=run.decision_run_id,
                portfolio_book_id=book_id,
                security_id=sec_id,
                symbol="TEST",
                side=OrderSide.BUY,
                quantity=Decimal("100"),
                price=Decimal("50.00"),
                fill_key="b1",
                idempotency_key="ik-1",
            )
        )
        store.book_fill(
            FillBookingCommand(
                order_id=uuid4(),
                decision_run_id=run.decision_run_id,
                portfolio_book_id=book_id,
                security_id=sec_id,
                symbol="TEST",
                side=OrderSide.SELL,
                quantity=Decimal("30"),
                price=Decimal("55.00"),
                fill_key="s1",
                idempotency_key="ik-2",
            )
        )

        store.rebuild_projections(book_id)
        positions = store.list_positions(book_id)
        assert len(positions) == 1
        assert positions[0].quantity == Decimal("70")

    def test_rebuild_projections_empty_after_sell_all(self) -> None:
        store = FakeOperationalStore()
        book_id = uuid4()
        sec_id = uuid4()
        svid = uuid4()
        now = datetime.now(UTC)
        run = store.reserve_run(
            RunReservation(
                run_key="proj-empty-test",
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

        store.book_fill(
            FillBookingCommand(
                order_id=uuid4(),
                decision_run_id=run.decision_run_id,
                portfolio_book_id=book_id,
                security_id=sec_id,
                symbol="TEST",
                side=OrderSide.BUY,
                quantity=Decimal("100"),
                price=Decimal("50.00"),
                fill_key="b1",
                idempotency_key="ik-1",
            )
        )
        store.book_fill(
            FillBookingCommand(
                order_id=uuid4(),
                decision_run_id=run.decision_run_id,
                portfolio_book_id=book_id,
                security_id=sec_id,
                symbol="TEST",
                side=OrderSide.SELL,
                quantity=Decimal("100"),
                price=Decimal("55.00"),
                fill_key="s1",
                idempotency_key="ik-2",
            )
        )
        store.rebuild_projections(book_id)
        positions = store.list_positions(book_id)
        assert len(positions) == 0


class TestFakeCommands:
    def test_submit_and_claim_command(self) -> None:
        store = FakeOperationalStore()
        envelope = CommandEnvelope(
            type="test_action",
            idempotency_key="ik-001",
            actor_id="operator",
            actor_display_name="Operator",
            book_id=uuid4(),
        )
        cmd = store.submit_command(envelope)
        assert cmd.status == CommandStatus.REQUESTED

        store.queue_command(cmd.command_id)
        claimed = store.claim_command()
        assert claimed is not None
        assert claimed.status == CommandStatus.RUNNING

        store.complete_command(cmd.command_id, CommandStatus.SUCCEEDED, result="done")
        completed = store.get_command(cmd.command_id)
        assert completed is not None
        assert completed.status == CommandStatus.SUCCEEDED
        assert completed.finished_at is not None

    def test_get_command_by_idempotency(self) -> None:
        store = FakeOperationalStore()
        envelope = CommandEnvelope(
            type="test_action",
            idempotency_key="uniq-001",
            actor_id="op1",
            actor_display_name="Op1",
        )
        store.submit_command(envelope)

        found = store.get_command_by_idempotency("op1", "test_action", "uniq-001")
        assert found is not None

        missing = store.get_command_by_idempotency("op1", "test_action", "nonexistent")
        assert missing is None

    def test_count_pending_commands(self) -> None:
        store = FakeOperationalStore()
        assert store.count_pending_commands() == 0
        envelope = CommandEnvelope(
            type="test",
            idempotency_key="ik-1",
            actor_id="op1",
            actor_display_name="Op1",
        )
        store.submit_command(envelope)
        assert store.count_pending_commands() == 1


class TestFakeScorecards:
    def test_save_and_load_scorecard(self) -> None:
        store = FakeOperationalStore()
        sc = Scorecard(
            symbol="AAPL",
            security_id="sec-1",
            facts_hash="abc",
            config_hash="def",
            strategy_version="sv-1",
            recommendation=Recommendation.hold,
            total_score=75.0,
            components=[
                ScorecardComponent(name="momentum", category="technical", score=80.0),
            ],
        )
        scorecard_id = store.save_scorecard(sc, "run-001")
        assert scorecard_id != ""

        loaded = store.load_scorecard(scorecard_id)
        assert loaded is not None
        assert loaded.symbol == "AAPL"

    def test_load_scorecards_for_run(self) -> None:
        store = FakeOperationalStore()
        sc1 = Scorecard(
            symbol="AAPL",
            security_id="sec-1",
            facts_hash="abc",
            config_hash="def",
            strategy_version="sv-1",
        )
        sc2 = Scorecard(
            symbol="MSFT",
            security_id="sec-2",
            facts_hash="abc",
            config_hash="def",
            strategy_version="sv-1",
        )
        store.save_scorecard(sc1, "run-001")
        store.save_scorecard(sc2, "run-001")

        run_scs = store.load_scorecards_for_run("run-001")
        assert len(run_scs) == 2

    def test_save_scorecard_requires_security_id(self) -> None:
        store = FakeOperationalStore()
        sc = Scorecard(
            symbol="AAPL",
            security_id="",
            facts_hash="abc",
            config_hash="def",
            strategy_version="sv-1",
        )
        with pytest.raises(ValueError, match="security_id"):
            store.save_scorecard(sc, "run-001")

    def test_save_scorecard_requires_facts_hash(self) -> None:
        store = FakeOperationalStore()
        sc = Scorecard(
            symbol="AAPL",
            security_id="sec-1",
            facts_hash="",
            config_hash="def",
            strategy_version="sv-1",
        )
        with pytest.raises(ValueError, match="facts_hash"):
            store.save_scorecard(sc, "run-001")

    def test_save_scorecard_requires_config_hash(self) -> None:
        store = FakeOperationalStore()
        sc = Scorecard(
            symbol="AAPL",
            security_id="sec-1",
            facts_hash="abc",
            config_hash="",
            strategy_version="sv-1",
        )
        with pytest.raises(ValueError, match="config_hash"):
            store.save_scorecard(sc, "run-001")

    def test_save_scorecard_requires_strategy_version(self) -> None:
        store = FakeOperationalStore()
        sc = Scorecard(
            symbol="AAPL",
            security_id="sec-1",
            facts_hash="abc",
            config_hash="def",
            strategy_version="",
        )
        with pytest.raises(ValueError, match="strategy_version"):
            store.save_scorecard(sc, "run-001")


class TestFakeConfig:
    def test_config_get_set(self) -> None:
        store = FakeOperationalStore()
        assert store.config_get("mock_mode") is None
        assert store.config_get("mock_mode", "false") == "false"

        store.config_set("mock_mode", "true")
        assert store.config_get("mock_mode") == "true"

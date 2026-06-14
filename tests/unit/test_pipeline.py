"""Unit tests for pipeline core flow (alpha_quant.app.pipeline)."""

from datetime import date
from unittest.mock import patch

from alpha_quant.app.pipeline import RunResult, run
from alpha_quant.domain.invariants import InvariantViolation
from alpha_quant.domain.models import Bar, PortfolioSnapshot, Position
from alpha_quant.domain.risk import RiskConfig


def _bar(open_v: float = 100.0) -> Bar:
    return Bar(
        symbol="_",
        date=date(2026, 6, 11),
        open=open_v,
        high=open_v + 1.0,
        low=open_v - 1.0,
        close=open_v,
        volume=1_000_000,
    )


def _make_bars(count: int = 400, start_price: float = 100.0) -> list[Bar]:
    bars: list[Bar] = []
    for i in range(count):
        d = date.fromordinal(date(2025, 1, 1).toordinal() + i)
        p = start_price + (i * 0.1)
        bars.append(
            Bar(
                symbol="_",
                date=d,
                open=p,
                high=p + 1.0,
                low=p - 1.0,
                close=p + 0.5,
                volume=1_000_000,
            )
        )
    return bars


class _FakeStore:
    def __init__(
        self,
        bars: dict[str, list[Bar]] | None = None,
        snapshots: list[PortfolioSnapshot] | None = None,
    ) -> None:
        self._bars = bars or {}
        self._positions: list[Position] = []
        self.saved_events: list[object] = []
        self._snapshots = snapshots or []

    def load_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        return self._bars.get(symbol, [])

    def load_positions(self) -> list[Position]:
        return self._positions

    def load_latest_portfolio_snapshot(self, book: str = "PAPER") -> PortfolioSnapshot | None:
        matching = [s for s in self._snapshots if s.book == book]
        return max(matching, key=lambda s: s.date) if matching else None

    def save_position(self, position: Position) -> None:
        for i, p in enumerate(self._positions):
            if p.symbol == position.symbol:
                self._positions[i] = position
                return
        self._positions.append(position)

    def save_fill(self, fill: object) -> None:
        pass

    def save_event(self, event: object) -> None:
        self.saved_events.append(event)

    def save_portfolio_snapshot(self, snapshot: object) -> None:
        pass

    def load_portfolio_snapshots(
        self, book: str = "PAPER", limit: int = 500
    ) -> list[PortfolioSnapshot]:
        matching = sorted(
            [s for s in self._snapshots if s.book == book],
            key=lambda s: s.date,
        )
        return matching[:limit]

    def transaction(self) -> object:
        class _Txn:
            def __enter__(self) -> object:  # noqa: N805
                return self

            def __exit__(self, *args: object) -> None:  # noqa: N805
                pass

        return _Txn()


class TestPipelineCore:
    def test_early_return_no_spy(self) -> None:
        store = _FakeStore()
        result = run(
            run_date=date(2026, 6, 11),
            store=store,
            universe=["AAPL"],
        )
        assert isinstance(result, RunResult)
        assert len(result.decisions) == 0
        assert result.halted is False

    def test_bar_loading_per_symbol(self) -> None:
        spy_bars = _make_bars(400, 100.0)
        aapl_bars = _make_bars(400, 150.0)
        store = _FakeStore(bars={"SPY": spy_bars, "AAPL": aapl_bars})
        with (
            patch("alpha_quant.app.pipeline.backfill_indicator_state") as mock_backfill,
            patch("alpha_quant.app.pipeline.detect_regime_and_multiplier") as mock_regime,
        ):
            mock_backfill.return_value = _FakeIndicatorState()
            mock_regime.return_value = ("RISK_ON", 1.0)
            result = run(
                run_date=date(2026, 6, 11),
                store=store,
                universe=["SPY", "AAPL"],
            )
        assert isinstance(result, RunResult)
        assert not result.halted

    def test_regime_detection(self) -> None:
        spy_bars = _make_bars(400, 100.0)
        aapl_bars = _make_bars(400, 150.0)
        store = _FakeStore(bars={"SPY": spy_bars, "AAPL": aapl_bars})
        with (
            patch("alpha_quant.app.pipeline.backfill_indicator_state") as mock_backfill,
            patch("alpha_quant.app.pipeline.detect_regime_and_multiplier") as mock_regime,
        ):
            mock_backfill.return_value = _FakeIndicatorState()
            mock_regime.return_value = ("RISK_OFF", 0.0)
            result = run(
                run_date=date(2026, 6, 11),
                store=store,
                universe=["SPY", "AAPL"],
                risk_config=RiskConfig(),
            )
        assert isinstance(result, RunResult)

    def test_risk_exits(self) -> None:
        spy_bars = _make_bars(400, 100.0)
        aapl_bars = _make_bars(400, 150.0)
        store = _FakeStore(bars={"SPY": spy_bars, "AAPL": aapl_bars})
        store._positions = [
            Position(
                symbol="AAPL",
                quantity=100.0,
                entry_price=150.0,
                avg_cost=150.0,
                current_price=150.0,
                stop_price=130.0,
                market_value=15_000.0,
            )
        ]
        with (
            patch("alpha_quant.app.pipeline.backfill_indicator_state") as mock_backfill,
            patch("alpha_quant.app.pipeline.detect_regime_and_multiplier") as mock_regime,
            patch("alpha_quant.app.pipeline.evaluate_risk_actions") as mock_risk,
        ):
            mock_backfill.return_value = _FakeIndicatorState()
            mock_regime.return_value = ("RISK_ON", 1.0)
            mock_risk.return_value = []
            result = run(
                run_date=date(2026, 6, 11),
                store=store,
                universe=["SPY", "AAPL"],
                risk_config=RiskConfig(),
            )
        assert isinstance(result, RunResult)

    def test_scoring_ranking_sizing(self) -> None:
        spy_bars = _make_bars(400, 100.0)
        aapl_bars = _make_bars(400, 150.0)
        store = _FakeStore(bars={"SPY": spy_bars, "AAPL": aapl_bars})
        with (
            patch("alpha_quant.app.pipeline.backfill_indicator_state") as mock_backfill,
            patch("alpha_quant.app.pipeline.detect_regime_and_multiplier") as mock_regime,
            patch("alpha_quant.app.pipeline.ensure_spy") as mock_ensure,
            patch("alpha_quant.app.pipeline.get_bar_for_date") as mock_bar,
            patch("alpha_quant.app.pipeline.decide_candidates") as mock_decide,
            patch("alpha_quant.app.pipeline.rank_candidates") as mock_rank,
            patch("alpha_quant.app.pipeline.compute_atr") as mock_atr,
            patch("alpha_quant.app.pipeline.size_entry") as mock_size,
        ):
            mock_backfill.return_value = _FakeIndicatorState()
            mock_regime.return_value = ("RISK_ON", 1.0)
            mock_ensure.return_value = ["AAPL", "SPY"]
            mock_bar.side_effect = lambda *a, **kw: (
                a[-1] if a and isinstance(a[-1], Bar) else _bar(100.0)
            )
            mock_decide.return_value = [_FakeCandidate()]
            mock_rank.return_value = [_FakeCandidate()]
            mock_atr.return_value = 2.0
            mock_size.return_value = type(
                "Sized",
                (),
                {"shares": 100, "notional": 10_000.0, "risk_at_stop": 200.0, "capped_by": None},
            )()
            result = run(
                run_date=date(2026, 6, 11),
                store=store,
                universe=["AAPL"],
            )
        assert isinstance(result, RunResult)

    def test_self_consistency_check(self) -> None:
        spy_bars = _make_bars(400, 100.0)
        aapl_bars = _make_bars(400, 150.0)
        store = _FakeStore(bars={"SPY": spy_bars, "AAPL": aapl_bars})
        store._positions = [
            Position(
                symbol="AAPL",
                quantity=100.0,
                entry_price=150.0,
                avg_cost=150.0,
                current_price=150.0,
                market_value=-1.0,
                stop_price=130.0,
            )
        ]
        with (
            patch("alpha_quant.app.pipeline.backfill_indicator_state") as mock_backfill,
            patch("alpha_quant.app.pipeline.detect_regime_and_multiplier") as mock_regime,
            patch("alpha_quant.app.pipeline.ensure_spy") as mock_ensure,
            patch("alpha_quant.app.pipeline.check_invariants") as mock_ci,
        ):
            mock_backfill.return_value = _FakeIndicatorState()
            mock_regime.return_value = ("RISK_ON", 1.0)
            mock_ensure.return_value = ["AAPL", "SPY"]
            mock_ci.return_value = [
                InvariantViolation(check="I1_test", detail="test")
            ]
            result = run(
                run_date=date(2026, 6, 11),
                store=store,
                universe=["AAPL"],
            )
        assert isinstance(result, RunResult)
        assert len(result.violations) > 0

    def test_abort_on_validate_halt(self) -> None:
        spy_bars = _make_bars(400, 100.0)
        aapl_bars = _make_bars(400, 150.0)
        store = _FakeStore(bars={"SPY": spy_bars, "AAPL": aapl_bars})
        with (
            patch("alpha_quant.app.pipeline.validate_bars") as mock_validate,
            patch("alpha_quant.app.pipeline.backfill_indicator_state") as mock_backfill,
            patch("alpha_quant.app.pipeline.detect_regime_and_multiplier") as mock_regime,
        ):
            mock_validate.return_value = [
                type("VR", (), {"check": "test", "issues": ["halt"], "severity": "HALT"})()
            ]
            mock_backfill.return_value = _FakeIndicatorState()
            mock_regime.return_value = ("RISK_ON", 1.0)
            result = run(
                run_date=date(2026, 6, 11),
                store=store,
                universe=["SPY", "AAPL"],
            )
        assert result.halted is True

    def test_drawdown_reduces_entry_sizing(self) -> None:
        spy_bars = _make_bars(400, 100.0)
        aapl_bars = _make_bars(400, 150.0)
        snapshots = [
            PortfolioSnapshot(date=date(2026, 6, 10), cash=80_000.0, equity=80_000.0),
            PortfolioSnapshot(date=date(2026, 6, 9), cash=100_000.0, equity=100_000.0),
        ]
        store = _FakeStore(bars={"SPY": spy_bars, "AAPL": aapl_bars}, snapshots=snapshots)
        with (
            patch("alpha_quant.app.pipeline.backfill_indicator_state") as mock_backfill,
            patch("alpha_quant.app.pipeline.detect_regime_and_multiplier") as mock_regime,
        ):
            mock_backfill.return_value = _FakeIndicatorState()
            mock_regime.return_value = ("RISK_ON", 1.0)
            result = run(
                run_date=date(2026, 6, 11),
                store=store,
                universe=["SPY", "AAPL"],
                risk_config=RiskConfig(dd_ladder=[[0.1, 0.5]]),
                prev_equity=100_000.0,
            )
        assert isinstance(result, RunResult)
        dd_events = [e for e in result.events if getattr(e, "action_type", None) == "drawdown_cut"]
        assert len(dd_events) > 0, "drawdown_cut event should be emitted when equity drops 20%"

    def test_daily_halt_on_equity_drop(self) -> None:
        spy_bars = _make_bars(400, 100.0)
        aapl_bars = _make_bars(400, 150.0)
        # Prev snapshot had equity=100K but only cash=50K (50K was in positions
        # that are now gone) → today_equity = 50K, daily loss = 50% → halt
        snapshots = [
            PortfolioSnapshot(date=date(2026, 6, 10), cash=50_000.0, equity=100_000.0),
        ]
        store = _FakeStore(bars={"SPY": spy_bars, "AAPL": aapl_bars}, snapshots=snapshots)
        with (
            patch("alpha_quant.app.pipeline.backfill_indicator_state") as mock_backfill,
            patch("alpha_quant.app.pipeline.detect_regime_and_multiplier") as mock_regime,
        ):
            mock_backfill.return_value = _FakeIndicatorState()
            mock_regime.return_value = ("RISK_ON", 1.0)
            result = run(
                run_date=date(2026, 6, 11),
                store=store,
                universe=["SPY", "AAPL"],
                risk_config=RiskConfig(daily_loss_halt_pct=0.01),
            )
        assert isinstance(result, RunResult)
        halt_events = [e for e in result.events if hasattr(e, "action_type") and e.action_type == "daily_halt"]
        assert len(halt_events) > 0, "daily_halt should emit when equity drops from 100K to 50K"

    def test_m1_missing_bars_skips_symbol(self) -> None:
        """Symbol with no bars produces no decision."""
        spy_bars = _make_bars(400, 100.0)
        store = _FakeStore(bars={"SPY": spy_bars})
        with (
            patch("alpha_quant.app.pipeline.backfill_indicator_state") as mock_backfill,
            patch("alpha_quant.app.pipeline.detect_regime_and_multiplier") as mock_regime,
        ):
            mock_backfill.return_value = _FakeIndicatorState()
            mock_regime.return_value = ("RISK_ON", 1.0)
            result = run(
                run_date=date(2026, 6, 11),
                store=store,
                universe=["SPY", "AAPL"],
                risk_config=RiskConfig(),
                prev_equity=100_000.0,
            )
        assert isinstance(result, RunResult)
        aapl_decisions = [d for d in result.decisions if d.symbol == "AAPL"]
        assert len(aapl_decisions) == 0, "AAPL should have no decisions (no bars)"

    def test_m2_regime_off_blocks_entries(self) -> None:
        """RISK_OFF regime (regime_mult=0) produces no entry decisions."""
        spy_bars = _make_bars(400, 100.0)
        aapl_bars = _make_bars(400, 150.0)
        store = _FakeStore(bars={"SPY": spy_bars, "AAPL": aapl_bars})
        with (
            patch("alpha_quant.app.pipeline.backfill_indicator_state") as mock_backfill,
            patch("alpha_quant.app.pipeline.detect_regime_and_multiplier") as mock_regime,
        ):
            mock_backfill.return_value = _FakeIndicatorState()
            mock_regime.return_value = ("RISK_OFF", 0.0)
            result = run(
                run_date=date(2026, 6, 11),
                store=store,
                universe=["SPY", "AAPL"],
                risk_config=RiskConfig(),
                prev_equity=100_000.0,
            )
        assert isinstance(result, RunResult)
        entry_decisions = [d for d in result.decisions if d.action == "enter"]
        assert len(entry_decisions) == 0, "RISK_OFF should prevent entries"

    def test_gate_blocked_emits_candidate_blocked_events(self) -> None:
        """Blocked candidates produce CandidateBlocked events with gate info."""
        spy_bars = _make_bars(400, 100.0)
        aapl_bars = _make_bars(400, 150.0)
        store = _FakeStore(bars={"SPY": spy_bars, "AAPL": aapl_bars})
        with (
            patch("alpha_quant.app.pipeline.backfill_indicator_state") as mock_backfill,
            patch("alpha_quant.app.pipeline.detect_regime_and_multiplier") as mock_regime,
            patch("alpha_quant.app.pipeline.decide_candidates") as mock_decide,
        ):
            mock_backfill.return_value = _FakeIndicatorState()
            mock_regime.return_value = ("RISK_ON", 1.0)
            blocked = _FakeCandidate()
            blocked.block_reason = "low_quality"
            blocked.gate_results = {"fundamental": False, "insider": True, "crowding": True, "blackout": True}
            mock_decide.return_value = [blocked]
            result = run(
                run_date=date(2026, 6, 11),
                store=store,
                universe=["SPY", "AAPL"],
                risk_config=RiskConfig(),
                prev_equity=100_000.0,
            )
        assert isinstance(result, RunResult)
        blocked_events = [e for e in result.events if type(e).__name__ == "CandidateBlocked"]
        assert len(blocked_events) > 0, "blocked candidate should produce CandidateBlocked events"

    def test_mark_to_market_updates_positions(self) -> None:
        spy_bars = _make_bars(400, 100.0)
        aapl_bars = _make_bars(400, 150.0)
        snapshots = [
            PortfolioSnapshot(date=date(2026, 6, 10), cash=100_000.0, equity=100_000.0),
        ]
        store = _FakeStore(bars={"SPY": spy_bars, "AAPL": aapl_bars}, snapshots=snapshots)
        store._positions = [
            Position(
                symbol="AAPL",
                quantity=100.0,
                entry_price=150.0,
                avg_cost=150.0,
                current_price=150.0,
                stop_price=130.0,
                market_value=15_000.0,
            )
        ]
        with (
            patch("alpha_quant.app.pipeline.backfill_indicator_state") as mock_backfill,
            patch("alpha_quant.app.pipeline.detect_regime_and_multiplier") as mock_regime,
        ):
            mock_backfill.return_value = _FakeIndicatorState()
            mock_regime.return_value = ("RISK_ON", 1.0)
            result = run(
                run_date=date(2026, 6, 11),
                store=store,
                universe=["SPY", "AAPL"],
                risk_config=RiskConfig(stop_atr_mult=10.0),
                prev_equity=100_000.0,
            )
        assert isinstance(result, RunResult)
        updated_positions = store._positions
        aapl_pos = next((p for p in updated_positions if p.symbol == "AAPL"), None)
        assert aapl_pos is not None
        # AAPL bars end at ~150 + 200 = ~350, so price should be ~200
        assert aapl_pos.current_price is not None and aapl_pos.current_price > 150.0, (
            f"current_price should be updated from bars, got {aapl_pos.current_price}"
        )

    def test_invariant_check_formats_consistency_violation(self) -> None:
        """Pipeline formats each invariant violation as a ConsistencyViolation event."""
        spy_bars = _make_bars(400, 100.0)
        aapl_bars = _make_bars(400, 150.0)
        snapshots = [
            PortfolioSnapshot(date=date(2026, 6, 10), cash=100_000.0, equity=100_000.0),
        ]
        store = _FakeStore(bars={"SPY": spy_bars, "AAPL": aapl_bars}, snapshots=snapshots)
        store._positions = [
            Position(
                symbol="AAPL",
                quantity=100.0,
                entry_price=150.0,
                avg_cost=150.0,
                current_price=150.0,
                stop_price=130.0,
                market_value=15_000.0,
            )
        ]
        with (
            patch("alpha_quant.app.pipeline.backfill_indicator_state") as mock_backfill,
            patch("alpha_quant.app.pipeline.detect_regime_and_multiplier") as mock_regime,
            patch("alpha_quant.app.pipeline.check_invariants") as mock_ci,
        ):
            mock_backfill.return_value = _FakeIndicatorState()
            mock_regime.return_value = ("RISK_ON", 1.0)
            mock_ci.return_value = [
                InvariantViolation(check="I1_test", detail="test")
            ]
            result = run(
                run_date=date(2026, 6, 11),
                store=store,
                universe=["SPY", "AAPL"],
                risk_config=RiskConfig(),
                prev_equity=100_000.0,
            )
        assert isinstance(result, RunResult)
        assert any(
            getattr(e, "check", None) == "I1_test"
            for e in result.events
        ), "check_invariants violations should produce ConsistencyViolation events"
        mock_ci.assert_called_once()


class _FakeIndicatorState:
    symbol = "SPY"
    date = date(2026, 6, 11)
    values: dict[str, float] = {
        "ema12": 100.0,
        "ema20": 99.0,
        "ema50": 98.0,
        "ema200": 95.0,
        "rsi": 55.0,
        "atr": 2.0,
        "macd": 1.0,
        "macd_signal": 0.5,
        "macd_hist": 0.5,
    }
    status: str = "ok"


class _FakeCandidate:
    symbol = "AAPL"
    date = date(2026, 6, 11)
    block_reason: str | None = None
    composite_score: float = 0.8
    scores: dict[str, float] = {"technical": 0.8, "momentum": 0.3}
    gate_results: dict[str, bool] = {"fundamental": True, "insider": True, "crowding": True, "blackout": True}
    regime: str = "RISK_ON"
    sector: str | None = None

    def model_copy(self, *, update: dict | None = None) -> _FakeCandidate:
        c = _FakeCandidate()
        for k, v in self.__dict__.items():
            setattr(c, k, v)
        if update:
            for k, v in update.items():
                setattr(c, k, v)
        return c


class TestDecideCandidates:
    """Behavioral tests for shared decide_candidates() gates M4–M7 (AC #10)."""

    def test_m7_earnings_blackout_blocks(self) -> None:
        from datetime import date

        from alpha_quant.app._loop import MechanismData, decide_candidates
        from alpha_quant.domain.models import EarningsEntry

        mech_data = MechanismData(
            earnings={
                "AAPL": [EarningsEntry(symbol="AAPL", date=date(2026, 6, 12), fiscal_quarter="Q2")],
            },
        )
        bars = {"AAPL": [Bar(symbol="AAPL", date=date(2026, 6, 11), open=100, high=101, low=99, close=100, volume=1_000_000)]}
        states = {"AAPL": _FakeIndicatorState()}

        with (
            patch("alpha_quant.app._loop.score_candidate") as mock_score,
            patch("alpha_quant.app._loop.check_blackout") as mock_bo,
        ):
            mock_score.return_value = _FakeCandidate()
            mock_bo.return_value = "BLOCK"

            result = decide_candidates(
                ["AAPL"], bars, states, date(2026, 6, 11), "RISK_ON", mech_data
            )

        assert len(result) == 1
        assert result[0].block_reason == "earnings_blackout"
        assert result[0].gate_results["blackout"] is False

    def test_m4_fundamental_blocks(self) -> None:
        from datetime import date

        from alpha_quant.app._loop import MechanismData, decide_candidates
        from alpha_quant.domain.fundamental import QualityVerdict
        from alpha_quant.domain.models import EarningsEntry, FundamentalsSnapshot

        mech_data = MechanismData(
            fundamentals={"AAPL": FundamentalsSnapshot(symbol="AAPL", as_of_date=date(2026, 6, 11), market_cap=1e12)},
            earnings={"AAPL": [EarningsEntry(symbol="AAPL", date=date(2026, 3, 1), fiscal_quarter="Q1")]},
        )
        bars = {"AAPL": [Bar(symbol="AAPL", date=date(2026, 6, 11), open=100, high=101, low=99, close=100, volume=1_000_000)]}
        states = {"AAPL": _FakeIndicatorState()}

        with (
            patch("alpha_quant.app._loop.score_candidate") as mock_score,
            patch("alpha_quant.app._loop.evaluate_fundamental") as mock_fund,
            patch("alpha_quant.app._loop.check_blackout") as mock_bo,
        ):
            mock_score.return_value = _FakeCandidate()
            mock_fund.return_value = QualityVerdict(passed=False, reason="low_quality")
            mock_bo.return_value = None

            result = decide_candidates(
                ["AAPL"], bars, states, date(2026, 6, 11), "RISK_ON", mech_data
            )

        assert len(result) == 1
        assert result[0].block_reason == "low_quality"
        assert result[0].gate_results["fundamental"] is False

    def test_m5_insider_blocks_on_negative_signal(self) -> None:
        from datetime import date

        from alpha_quant.app._loop import MechanismData, decide_candidates
        from alpha_quant.domain.fundamental import QualityVerdict
        from alpha_quant.domain.insider_signal import InsiderVerdict
        from alpha_quant.domain.models import EarningsEntry, FundamentalsSnapshot, InsiderTransaction

        mech_data = MechanismData(
            fundamentals={"AAPL": FundamentalsSnapshot(symbol="AAPL", as_of_date=date(2026, 6, 11), market_cap=1e12)},
            insider_txns={"AAPL": [InsiderTransaction(symbol="AAPL", filing_date=date(2026, 6, 10), transaction_date=date(2026, 6, 8), owner="CEO", title="CEO", transaction_type="Sell", shares_traded=-10000, price=100, shares_held=50000)]},
            earnings={"AAPL": [EarningsEntry(symbol="AAPL", date=date(2026, 3, 1), fiscal_quarter="Q1")]},
        )
        bars = {"AAPL": [Bar(symbol="AAPL", date=date(2026, 6, 11), open=100, high=101, low=99, close=100, volume=1_000_000)]}
        states = {"AAPL": _FakeIndicatorState()}

        with (
            patch("alpha_quant.app._loop.score_candidate") as mock_score,
            patch("alpha_quant.app._loop.evaluate_fundamental") as mock_fund,
            patch("alpha_quant.app._loop.check_blackout") as mock_bo,
            patch("alpha_quant.app._loop.evaluate_insider") as mock_insider,
        ):
            mock_score.return_value = _FakeCandidate()
            mock_fund.return_value = QualityVerdict(passed=True, reason=None)
            mock_bo.return_value = None
            mock_insider.return_value = InsiderVerdict(score=-1.0, reason="insider_selling")

            result = decide_candidates(
                ["AAPL"], bars, states, date(2026, 6, 11), "RISK_ON", mech_data
            )

        assert len(result) == 1
        assert result[0].block_reason == "insider_selling"
        assert result[0].gate_results["insider"] is False

    def test_m6_crowding_blocks(self) -> None:
        from datetime import date

        from alpha_quant.app._loop import MechanismData, decide_candidates
        from alpha_quant.domain.crowding import CrowdingVerdict
        from alpha_quant.domain.models import EarningsEntry, MentionCount

        mention_dates = [date(2026, 6, d) for d in range(1, 12)]
        mech_data = MechanismData(
            mentions={
                "AAPL": [MentionCount(symbol="AAPL", mention_date=d, source="twitter", count=500)
                         for d in mention_dates] +
                        [MentionCount(symbol="AAPL", mention_date=date(2026, 6, 11), source="twitter", count=5000)],
            },
            earnings={"AAPL": [EarningsEntry(symbol="AAPL", date=date(2026, 3, 1), fiscal_quarter="Q1")]},
        )
        bars = {"AAPL": [Bar(symbol="AAPL", date=date(2026, 6, 11), open=100, high=101, low=99, close=100, volume=1_000_000)]}
        states = {"AAPL": _FakeIndicatorState()}

        with (
            patch("alpha_quant.app._loop.score_candidate") as mock_score,
            patch("alpha_quant.app._loop.check_blackout") as mock_bo,
            patch("alpha_quant.app._loop.evaluate_crowding") as mock_crowd,
        ):
            mock_score.return_value = _FakeCandidate()
            mock_bo.return_value = None
            mock_crowd.return_value = CrowdingVerdict(blocked=True, reason="high_mentions", blocked_until=None)

            result = decide_candidates(
                ["AAPL"], bars, states, date(2026, 6, 11), "RISK_ON", mech_data
            )

        assert len(result) == 1
        assert result[0].block_reason == "high_mentions"
        assert result[0].gate_results["crowding"] is False

    def test_all_gates_pass_with_extra_scores(self) -> None:
        from datetime import date

        from alpha_quant.app._loop import MechanismData, decide_candidates
        from alpha_quant.domain.crowding import CrowdingVerdict
        from alpha_quant.domain.fundamental import QualityVerdict
        from alpha_quant.domain.insider_signal import InsiderVerdict
        from alpha_quant.domain.models import EarningsEntry, FundamentalsSnapshot, InsiderTransaction, MentionCount

        mech_data = MechanismData(
            fundamentals={"AAPL": FundamentalsSnapshot(symbol="AAPL", as_of_date=date(2026, 6, 11), market_cap=1e12)},
            insider_txns={"AAPL": [InsiderTransaction(symbol="AAPL", filing_date=date(2026, 6, 10), transaction_date=date(2026, 6, 8), owner="CEO", title="CEO", transaction_type="Buy", shares_traded=5000, price=100, shares_held=55000)]},
            mentions={
                "AAPL": [MentionCount(symbol="AAPL", mention_date=date(2026, 6, 10), source="twitter", count=50)],
            },
            earnings={"AAPL": [EarningsEntry(symbol="AAPL", date=date(2026, 3, 1), fiscal_quarter="Q1")]},
        )
        bars = {"AAPL": [Bar(symbol="AAPL", date=date(2026, 6, 11), open=100, high=101, low=99, close=100, volume=1_000_000)]}
        states = {"AAPL": _FakeIndicatorState()}

        with (
            patch("alpha_quant.app._loop.score_candidate") as mock_score,
            patch("alpha_quant.app._loop.evaluate_fundamental") as mock_fund,
            patch("alpha_quant.app._loop.check_blackout") as mock_bo,
            patch("alpha_quant.app._loop.evaluate_insider") as mock_insider,
            patch("alpha_quant.app._loop.evaluate_crowding") as mock_crowd,
        ):
            mock_score.return_value = _FakeCandidate()
            mock_fund.return_value = QualityVerdict(passed=True, reason=None)
            mock_bo.return_value = None
            mock_insider.return_value = InsiderVerdict(score=2.5, reason=None)
            mock_crowd.return_value = CrowdingVerdict(blocked=False, blocked_until=None, reason=None)

            result = decide_candidates(
                ["AAPL"], bars, states, date(2026, 6, 11), "RISK_ON", mech_data
            )

        assert len(result) == 1
        assert result[0].block_reason is None
        for gate in ("fundamental", "insider", "crowding", "blackout"):
            assert result[0].gate_results[gate] is True, f"gate {gate} should pass"


class TestShadowAblation:
    """Behavioral tests for ablation toggles (AC #6, #7, #8)."""

    def test_no_insider_unblocks_negative_signal(self) -> None:
        """NO_INSIDER produces different outcome than FULL when M5 blocks."""
        from datetime import date

        from alpha_quant.app._loop import MechanismData, decide_candidates
        from alpha_quant.domain.ablation import AblationConfig
        from alpha_quant.domain.fundamental import QualityVerdict
        from alpha_quant.domain.insider_signal import InsiderVerdict
        from alpha_quant.domain.models import EarningsEntry, FundamentalsSnapshot, InsiderTransaction
    
        mech_data = MechanismData(
            fundamentals={"AAPL": FundamentalsSnapshot(symbol="AAPL", as_of_date=date(2026, 6, 11), market_cap=1e12)},
            insider_txns={"AAPL": [InsiderTransaction(symbol="AAPL", filing_date=date(2026, 6, 10), transaction_date=date(2026, 6, 8), owner="CEO", title="CEO", transaction_type="Sell", shares_traded=-10000, price=100, shares_held=50000)]},
            earnings={"AAPL": [EarningsEntry(symbol="AAPL", date=date(2026, 3, 1), fiscal_quarter="Q1")]},
        )
        bars = {"AAPL": [Bar(symbol="AAPL", date=date(2026, 6, 11), open=100, high=101, low=99, close=100, volume=1_000_000)]}
        states = {"AAPL": _FakeIndicatorState()}
        no_insider = AblationConfig(disable_insider=True)

        with (
            patch("alpha_quant.app._loop.score_candidate") as mock_score,
            patch("alpha_quant.app._loop.evaluate_fundamental") as mock_fund,
            patch("alpha_quant.app._loop.check_blackout") as mock_bo,
            patch("alpha_quant.app._loop.evaluate_insider") as mock_insider,
        ):
            mock_score.return_value = _FakeCandidate()
            mock_fund.return_value = QualityVerdict(passed=True, reason=None)
            mock_bo.return_value = None
            mock_insider.return_value = InsiderVerdict(score=-2.0, reason="insider_selling")

            full_result = decide_candidates(
                ["AAPL"], bars, states, date(2026, 6, 11), "RISK_ON", mech_data,
            )
            ablated_result = decide_candidates(
                ["AAPL"], bars, states, date(2026, 6, 11), "RISK_ON", mech_data,
                ablation=no_insider,
            )

        # FULL should block due to negative insider
        assert len(full_result) == 1
        assert full_result[0].block_reason is not None
        assert full_result[0].gate_results["insider"] is False

        # NO_INSIDER should pass (M5 skipped)
        assert len(ablated_result) == 1
        assert ablated_result[0].block_reason is None
        assert ablated_result[0].gate_results["insider"] is True

    def test_no_crowding_veto_unblocks_crowding_block(self) -> None:
        """NO_CROWDING_VETO produces different outcome than FULL when M6 blocks."""
        from datetime import date

        from alpha_quant.app._loop import MechanismData, decide_candidates
        from alpha_quant.domain.ablation import AblationConfig
        from alpha_quant.domain.crowding import CrowdingVerdict
        from alpha_quant.domain.models import EarningsEntry, MentionCount

        mech_data = MechanismData(
            mentions={"AAPL": [MentionCount(symbol="AAPL", mention_date=date(2026, 6, 10), source="twitter", count=1000)]},
            earnings={"AAPL": [EarningsEntry(symbol="AAPL", date=date(2026, 3, 1), fiscal_quarter="Q1")]},
        )
        bars = {"AAPL": [Bar(symbol="AAPL", date=date(2026, 6, 11), open=100, high=101, low=99, close=100, volume=1_000_000)]}
        states = {"AAPL": _FakeIndicatorState()}
        no_crowding = AblationConfig(disable_crowding_veto=True)

        with (
            patch("alpha_quant.app._loop.score_candidate") as mock_score,
            patch("alpha_quant.app._loop.check_blackout") as mock_bo,
            patch("alpha_quant.app._loop.evaluate_crowding") as mock_crowd,
        ):
            mock_score.return_value = _FakeCandidate()
            mock_bo.return_value = None
            mock_crowd.return_value = CrowdingVerdict(blocked=True, reason="high_mentions", blocked_until=None)

            full_result = decide_candidates(
                ["AAPL"], bars, states, date(2026, 6, 11), "RISK_ON", mech_data,
            )
            ablated_result = decide_candidates(
                ["AAPL"], bars, states, date(2026, 6, 11), "RISK_ON", mech_data,
                ablation=no_crowding,
            )

        # FULL should block due to crowding veto
        assert len(full_result) == 1
        assert full_result[0].block_reason is not None
        assert full_result[0].gate_results["crowding"] is False

        # NO_CROWDING_VETO should pass (M6 skipped)
        assert len(ablated_result) == 1
        assert ablated_result[0].block_reason is None
        assert ablated_result[0].gate_results["crowding"] is True

    def test_pipeline_accepts_shadow_books(self) -> None:
        """Pipeline.run processes shadow books and persists their snapshots."""
        from alpha_quant.app.pipeline import PipelineConfig, run as run_pipeline
        from alpha_quant.domain.ablation import AblationConfig, ShadowBook
        from alpha_quant.domain.fills import FillConfig

        spy_bars = _make_bars(400, 100.0)
        aapl_bars = _make_bars(400, 150.0)
        store = _FakeStore(bars={"SPY": spy_bars, "AAPL": aapl_bars})

        shadow_book = ShadowBook("TEST_SHADOW", AblationConfig(disable_insider=True))

        with (
            patch("alpha_quant.app.pipeline.backfill_indicator_state") as mock_backfill,
            patch("alpha_quant.app.pipeline.detect_regime_and_multiplier") as mock_regime,
            patch("alpha_quant.app.pipeline.decide_candidates") as mock_decide,
        ):
            mock_backfill.return_value = _FakeIndicatorState()
            mock_regime.return_value = ("RISK_ON", 1.0)
            mock_decide.return_value = [_FakeCandidate()]

            result = run_pipeline(
                run_date=date(2026, 6, 11),
                store=store,
                universe=["SPY", "AAPL"],
                config=PipelineConfig(ablation=AblationConfig()),
                fill_config=FillConfig(),
                shadow_books={"TEST_SHADOW": shadow_book},
            )

        assert isinstance(result, RunResult)
        assert result.run_id

    def test_backtest_accepts_ablation_config(self) -> None:
        """Backtest config passes ablation through to decide_candidates."""
        from alpha_quant.app.backtest import BacktestConfig, run_backtest
        from alpha_quant.domain.ablation import AblationConfig
        from alpha_quant.domain.fills import FillConfig

        spy_bars = _make_bars(400, 100.0)
        aapl_bars = _make_bars(400, 150.0)
        store = _FakeStore(bars={"SPY": spy_bars, "AAPL": aapl_bars})

        bt_config = BacktestConfig(
            start_date=date(2025, 1, 2),
            end_date=date(2025, 1, 15),
            symbols=["AAPL"],
            initial_equity=100_000.0,
            ablation=AblationConfig(disable_insider=True),
        )

        with (
            patch("alpha_quant.app.backtest.backfill_indicator_state") as mock_backfill,
            patch("alpha_quant.app.backtest.update_indicator_state") as mock_update,
            patch("alpha_quant.app.backtest.detect_regime_and_multiplier") as mock_regime,
            patch("alpha_quant.app.backtest.decide_candidates") as mock_decide,
        ):
            mock_backfill.return_value = _FakeIndicatorState()
            mock_update.return_value = _FakeIndicatorState()
            mock_regime.return_value = ("RISK_ON", 1.0)
            mock_decide.return_value = []

            result = run_backtest(
                config=bt_config,
                store=store,
                fill_config=FillConfig(),
            )

        # Verify ablation was passed to decide_candidates
        assert mock_decide.called
        _, kwargs = mock_decide.call_args
        assert kwargs.get("ablation") is not None
        assert kwargs["ablation"].disable_insider is True

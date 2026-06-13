"""Unit tests for pipeline core flow (alpha_quant.app.pipeline)."""

from datetime import date
from unittest.mock import patch

from alpha_quant.app.pipeline import RunResult, run
from alpha_quant.domain.models import Bar, Position
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
    def __init__(self, bars: dict[str, list[Bar]] | None = None) -> None:
        self._bars = bars or {}
        self._positions: list[Position] = []
        self.saved_events: list[object] = []

    def load_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        return self._bars.get(symbol, [])

    def load_positions(self) -> list[Position]:
        return self._positions

    def load_latest_portfolio_snapshot(self) -> None:
        return None

    def save_position(self, position: Position) -> None:
        pass

    def save_fill(self, fill: object) -> None:
        pass

    def save_event(self, event: object) -> None:
        self.saved_events.append(event)

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
            patch("alpha_quant.app.pipeline.score_candidate") as mock_score,
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
            mock_score.return_value = _FakeCandidate()
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
        ):
            mock_backfill.return_value = _FakeIndicatorState()
            mock_regime.return_value = ("RISK_ON", 1.0)
            mock_ensure.return_value = ["AAPL", "SPY"]
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
    composite_score: float = 0.8
    scores: dict[str, float] = {"technical": 0.8, "momentum": 0.3}
    regime: str = "RISK_ON"

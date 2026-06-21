from __future__ import annotations

from datetime import date

from app.pipeline_steps import derive_step, load_bars_step, validate_step
from domain.models import Bar
from ports.market_data import MarketData


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


class _FakeMarketData(MarketData):
    def __init__(self, bars: dict[str, list[Bar]]) -> None:
        self._bars = bars

    def daily_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        return [b for b in self._bars.get(symbol, []) if start <= b.date <= end]

    def latest_quote(self, symbol: str) -> object:
        return None

    def trading_calendar(self, start: date, end: date) -> list[object]:
        return []


class TestLoadBarsStep:
    def test_spy_only_in_market_data(self) -> None:
        md = _FakeMarketData({"SPY": _make_bars(400)})
        result = load_bars_step(
            run_date=date(2026, 6, 15),
            symbols=["SPY", "AAPL"],
            market_data=md,
            lookback_days=400,
            run_id="test-1",
        )
        assert "SPY" in result.all_bars
        assert "AAPL" not in result.all_bars
        assert any(e.event_type == "source_degraded" for e in result.events)

    def test_both_symbols_in_market_data(self) -> None:
        md = _FakeMarketData({"SPY": _make_bars(400), "AAPL": _make_bars(400, 150.0)})
        result = load_bars_step(
            run_date=date(2026, 6, 15),
            symbols=["SPY", "AAPL"],
            market_data=md,
            lookback_days=400,
            run_id="test-2",
        )
        assert "SPY" in result.all_bars
        assert "AAPL" in result.all_bars
        assert len(result.prices) == 2

    def test_prices_populated(self) -> None:
        md = _FakeMarketData({"SPY": _make_bars(400)})
        result = load_bars_step(
            run_date=date(2026, 6, 15),
            symbols=["SPY"],
            market_data=md,
            lookback_days=400,
            run_id="test-3",
        )
        assert "SPY" in result.prices
        assert result.prices["SPY"] > 0


class TestValidateStep:
    def test_valid_bars_no_violations(self) -> None:
        bars = _make_bars(400)
        result = validate_step(
            all_bars={"SPY": bars},
            run_id="test-4",
        )
        assert len(result.events) == 0
        assert not result.halted


class TestDeriveStep:
    def test_derive_indicator_state(self) -> None:
        bars = _make_bars(400)
        result = derive_step(
            all_bars={"SPY": bars},
            run_id="test-5",
        )
        assert "SPY" in result.indicator_states
        state = result.indicator_states["SPY"]
        assert state.values["bar_count"] > 0
        assert state.values["ema12"] > 0

    def test_derive_all_symbols(self) -> None:
        spy = _make_bars(400)
        aapl = _make_bars(400, 150.0)
        result = derive_step(
            all_bars={"SPY": spy, "AAPL": aapl},
            run_id="test-6",
        )
        assert "SPY" in result.indicator_states
        assert "AAPL" in result.indicator_states
        assert len(result.indicator_states) == 2

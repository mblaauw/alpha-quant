"""Integration tests for backtest metrics and lifecycle."""

from datetime import date, timedelta

from app.backtest import BacktestConfig, BacktestMetrics, run_backtest
from domain.models import Bar
from ports.market_data import MarketData


def _make_bars(symbol: str, count: int, start_price: float = 100.0) -> list[Bar]:
    bars: list[Bar] = []
    price = start_price
    for i in range(count):
        dt = date(2023, 1, 1) + timedelta(days=i)
        bars.append(
            Bar(
                symbol=symbol,
                date=dt,
                open=price,
                high=price * 1.02,
                low=price * 0.98,
                close=price * 1.001,
                volume=1_000_000,
            )
        )
        price *= 1.001
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


def test_backtest_runs_with_minimal_data() -> None:
    spy = _make_bars("SPY", 600, 400.0)
    aapl = _make_bars("AAPL", 600, 150.0)
    msft = _make_bars("MSFT", 600, 300.0)
    md = _FakeMarketData({"SPY": spy, "AAPL": aapl, "MSFT": msft})

    config = BacktestConfig(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 3, 31),
        symbols=["AAPL", "MSFT"],
        initial_equity=100_000.0,
        max_positions=5,
    )

    result = run_backtest(config=config, store=None, market_data=md)
    assert result.metrics.num_trades >= 0
    assert isinstance(result.metrics, BacktestMetrics)


def test_backtest_metrics_spy_benchmark() -> None:
    spy = _make_bars("SPY", 600, 400.0)
    aapl = _make_bars("AAPL", 600, 150.0)
    md = _FakeMarketData({"SPY": spy, "AAPL": aapl})

    config = BacktestConfig(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 3, 31),
        symbols=["AAPL"],
        initial_equity=100_000.0,
        max_positions=3,
    )

    result = run_backtest(config=config, store=None, market_data=md)
    assert result.metrics.spy_return_pct is not None

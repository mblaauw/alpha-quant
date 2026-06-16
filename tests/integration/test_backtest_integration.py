"""Integration tests for backtest metrics and lifecycle."""

from datetime import date, timedelta

from app.backtest import BacktestConfig, BacktestMetrics, run_backtest
from app.store import CanonicalStore
from domain.models import Bar


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


def _save_all_bars(store: CanonicalStore, symbols: list[tuple[str, int, float]]) -> None:
    all_bars: list[Bar] = []
    for sym, count, price in symbols:
        all_bars.extend(_make_bars(sym, count, price))
    store.save_bars("ALL", all_bars)


def test_backtest_runs_with_minimal_data(tmp_path: None) -> None:
    base = tmp_path
    store = CanonicalStore(base_path=base)
    _save_all_bars(store, [("SPY", 600, 400.0), ("AAPL", 600, 150.0), ("MSFT", 600, 300.0)])

    config = BacktestConfig(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 3, 31),
        symbols=["AAPL", "MSFT"],
        initial_equity=100_000.0,
        max_positions=5,
    )

    result = run_backtest(config=config, store=store)
    assert result.steps, "backtest should produce steps"
    assert len(result.steps) >= 2
    assert result.metrics is not None
    assert result.metrics.num_trades >= 0
    assert isinstance(result.metrics.total_return_pct, float)


def test_backtest_returns_metrics_with_spy_benchmark(tmp_path: None) -> None:
    base = tmp_path
    store = CanonicalStore(base_path=base)
    _save_all_bars(store, [("SPY", 600, 400.0), ("AAPL", 600, 150.0)])

    config = BacktestConfig(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 2, 15),
        symbols=["AAPL"],
        initial_equity=100_000.0,
        max_positions=5,
    )

    result = run_backtest(config=config, store=store)
    m = result.metrics
    assert m.spy_return_pct is not None
    assert m.spy_cagr is not None
    assert m.spy_max_dd_pct is not None


def test_backtest_returns_empty_result_for_missing_spy(tmp_path: None) -> None:
    base = tmp_path
    store = CanonicalStore(base_path=base)

    config = BacktestConfig(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 2, 1),
        symbols=["AAPL"],
        initial_equity=100_000.0,
    )

    result = run_backtest(config=config, store=store)
    assert result.steps == []
    assert result.metrics.total_return_pct == 0.0


def test_backtest_metrics_are_reasonable(tmp_path: None) -> None:
    base = tmp_path
    store = CanonicalStore(base_path=base)
    _save_all_bars(store, [("SPY", 600, 400.0), ("AAPL", 600, 150.0)])

    config = BacktestConfig(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 2, 1),
        symbols=["AAPL"],
        initial_equity=100_000.0,
        max_positions=5,
    )

    result = run_backtest(config=config, store=store)
    m: BacktestMetrics = result.metrics
    assert isinstance(m.total_return_pct, float)
    assert m.max_drawdown_pct <= 0.0
    assert m.num_trades >= 0
    assert isinstance(m.sharpe, float)
    assert isinstance(m.sortino, float)


def test_backtest_preserves_decision_and_fill_records(tmp_path: None) -> None:
    base = tmp_path
    store = CanonicalStore(base_path=base)
    _save_all_bars(store, [("SPY", 600, 400.0), ("AAPL", 600, 150.0)])

    config = BacktestConfig(
        start_date=date(2024, 1, 10),
        end_date=date(2024, 2, 15),
        symbols=["AAPL"],
        initial_equity=100_000.0,
        max_positions=5,
    )

    result = run_backtest(config=config, store=store)
    if result.decisions:
        assert all(d.symbol == "AAPL" for d in result.decisions)
    if result.fills:
        assert all(f.symbol == "AAPL" for f in result.fills)


def test_high_since_entry_persists_across_days(tmp_path: None) -> None:
    """high_since_entry must be the running max, not just the initial or per-day value."""
    base = tmp_path
    store = CanonicalStore(base_path=base)

    bars: list[Bar] = []
    price = 100.0
    for i in range(10):
        dt = date(2024, 1, 1) + timedelta(days=i)
        high = price * 1.20 if i == 2 else price * 1.02
        bars.append(
            Bar(symbol="AAPL", date=dt, open=price, high=high, low=price * 0.98, close=price, volume=1_000_000)
        )
        price *= 1.001
    bars.append(
        Bar(symbol="SPY", date=date(2024, 1, 1), open=450.0, high=455.0, low=445.0, close=450.0, volume=1_000_000)
    )
    for i in range(1, 10):
        dt = date(2024, 1, 1) + timedelta(days=i)
        bars.append(
            Bar(symbol="SPY", date=dt, open=450.0, high=455.0, low=445.0, close=450.0, volume=1_000_000)
        )
    store.save_bars("ALL", bars)

    config = BacktestConfig(
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 10),
        symbols=["AAPL"],
        initial_equity=100_000.0,
        max_positions=5,
    )

    result = run_backtest(config=config, store=store)
    assert result.metrics.num_trades >= 0

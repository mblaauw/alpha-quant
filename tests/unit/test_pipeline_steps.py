from __future__ import annotations

from datetime import date

from alpha_quant.app.pipeline_steps import derive_step, load_bars_step, validate_step
from alpha_quant.domain.models import Bar
from alpha_quant.ports.store import Store


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


class _FakeStore(Store):
    def __init__(
        self,
        bars: dict[str, list[Bar]] | None = None,
    ) -> None:
        self._bars = bars or {}

    def load_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        return self._bars.get(symbol, [])

    def save_bars(self, symbol: str, bars: list[Bar]) -> None:
        pass

    def load_decisions(self, symbol: str, since: date) -> list:
        return []

    def save_decision(self, decision: object) -> None:
        pass

    def load_order(self, order_id: str) -> None:
        return None

    def save_order(self, order: object) -> None:
        pass

    def load_fills(self, order_id: str) -> list:
        return []

    def save_fill(self, fill: object) -> None:
        pass

    def load_positions(self) -> list:
        return []

    def save_position(self, position: object) -> None:
        pass

    def save_event(self, event: object) -> None:
        pass

    def load_events(self, event_type: str | None = None, since: date | None = None) -> list:
        return []

    def save_indicator_state(self, state: object) -> None:
        pass

    def load_indicator_state(self, symbol: str, dt: date) -> None:
        return None

    def save_corp_actions(self, symbol: str, actions: list) -> None:
        pass

    def load_corp_actions(self, symbol: str) -> list:
        return []

    def save_earnings(self, symbol: str, entries: list) -> None:
        pass

    def load_earnings(self, symbol: str) -> list:
        return []

    def load_fundamentals(self, symbol: str) -> list:
        return []

    def load_insider_transactions(self, symbol: str) -> list:
        return []

    def load_mentions(self, symbol: str) -> list:
        return []

    def save_fundamentals(self, symbol: str, snapshots: list) -> None:
        pass

    def save_insider_transactions(self, symbol: str, txns: list) -> None:
        pass

    def save_mentions(self, symbol: str, mentions: list) -> None:
        pass

    def save_portfolio_snapshot(self, snapshot: object) -> None:
        pass

    def load_latest_portfolio_snapshot(self, book: str = "PAPER") -> None:
        return None

    def load_portfolio_snapshots(self, book: str = "PAPER", limit: int = 500) -> list:
        return []

    def save_journal(self, entry: object) -> None:
        pass

    def load_journal(self, dt: date) -> None:
        return None

    def save_report(self, report: object) -> None:
        pass

    def load_report(self, dt: date, report_type: str) -> None:
        return None

    def add_quarantine(self, symbol: str, reason: str, severity: str = "QUARANTINE") -> None:
        pass

    def list_quarantine(self, cleared: bool = False) -> list:
        return []

    def clear_quarantine(self, symbol: str) -> None:
        pass

    def register_run(self, run_type: str, config_hash: str, fixture_version: str = "") -> str:
        return "test-run-id"

    def complete_run(self, run_id: str, status: str = "completed", manifest_hash: str = "") -> None:
        pass

    def list_runs(self, since_date: date | None = None) -> list:
        return []

    def transaction(self) -> object:
        return self

    def close(self) -> None:
        pass


class TestLoadBarsStep:
    def test_spy_only_in_store(self) -> None:
        store = _FakeStore(bars={"SPY": _make_bars(400)})
        result = load_bars_step(
            run_date=date(2026, 6, 15),
            symbols=["SPY", "AAPL"],
            store=store,
            market_data=None,
            lookback_days=400,
            run_id="test-1",
        )
        assert "SPY" in result.all_bars
        assert "AAPL" not in result.all_bars
        assert any(e.event_type == "source_degraded" for e in result.events)

    def test_both_symbols_in_store(self) -> None:
        store = _FakeStore(bars={"SPY": _make_bars(400), "AAPL": _make_bars(400, 150.0)})
        result = load_bars_step(
            run_date=date(2026, 6, 15),
            symbols=["SPY", "AAPL"],
            store=store,
            market_data=None,
            lookback_days=400,
            run_id="test-2",
        )
        assert "SPY" in result.all_bars
        assert "AAPL" in result.all_bars
        assert len(result.prices) == 2

    def test_prices_populated(self) -> None:
        store = _FakeStore(bars={"SPY": _make_bars(400)})
        result = load_bars_step(
            run_date=date(2026, 6, 15),
            symbols=["SPY"],
            store=store,
            market_data=None,
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

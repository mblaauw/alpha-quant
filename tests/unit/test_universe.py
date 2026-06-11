from __future__ import annotations

from datetime import date, timedelta

from alpha_quant.domain.models import Bar, FundamentalsSnapshot
from alpha_quant.domain.universe import select
from alpha_quant.ports.fundamentals import Fundamentals
from alpha_quant.ports.market_data import MarketData


class FakeMarketData(MarketData):
    def __init__(self, bars: dict[str, list[Bar]]) -> None:
        self._bars = bars

    def daily_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        all_bars = self._bars.get(symbol, [])
        return [b for b in all_bars if start <= b.date <= end]

    def latest_quote(self, symbol: str) -> None:
        return None

    def trading_calendar(self, start: date, end: date) -> list:
        return []


class FakeFundamentals(Fundamentals):
    def __init__(self, data: dict[str, dict]) -> None:
        self._data = data

    def snapshot(self, symbol: str) -> FundamentalsSnapshot | None:
        return None

    def earnings_calendar(self, start: date, end: date) -> list:
        return []


def _make_bars(
    symbol: str, count: int, start_price: float = 100.0, volume: float = 1_000_000.0
) -> list[Bar]:
    bars: list[Bar] = []
    base = date(2026, 1, 1)
    price = start_price
    for i in range(count):
        d = base + timedelta(days=i)
        bars.append(
            Bar(
                symbol=symbol,
                date=d,
                open=price,
                high=price * 1.01,
                low=price * 0.99,
                close=price,
                volume=volume,
            )
        )
    return bars


class TestUniverseSelection:
    def test_passes_valid_symbol(self) -> None:
        dt = date(2026, 2, 1)
        bars = _make_bars("AAPL", 30)
        md = FakeMarketData({"AAPL": bars})
        fd = FakeFundamentals({})
        result = select(dt, ["AAPL"], md, fd)
        assert len(result) == 1
        assert result[0].symbol == "AAPL"
        assert result[0].passes_m1 is True

    def test_fails_low_price(self) -> None:
        dt = date(2026, 2, 1)
        bars = _make_bars("PENNY", 30, start_price=2.0)
        md = FakeMarketData({"PENNY": bars})
        fd = FakeFundamentals({})
        result = select(dt, ["PENNY"], md, fd)
        assert result[0].passes_m1 is False
        assert "below" in (result[0].fail_reason or "")

    def test_fails_low_adv(self) -> None:
        dt = date(2026, 2, 1)
        bars = _make_bars("SMALL", 30, start_price=10.0, volume=1_000.0)
        md = FakeMarketData({"SMALL": bars})
        fd = FakeFundamentals({})
        result = select(dt, ["SMALL"], md, fd)
        assert result[0].passes_m1 is False
        assert "ADV" in (result[0].fail_reason or "")

    def test_fails_quarantined(self) -> None:
        dt = date(2026, 2, 1)
        bars = _make_bars("BAD", 30)
        md = FakeMarketData({"BAD": bars})
        fd = FakeFundamentals({})
        result = select(dt, ["BAD"], md, fd, quarantined={"BAD"})
        assert result[0].passes_m1 is False
        assert "Quarantined" in (result[0].fail_reason or "")

    def test_fails_no_sec_map(self) -> None:
        dt = date(2026, 2, 1)
        bars = _make_bars("UNKNOWN", 30)
        md = FakeMarketData({"UNKNOWN": bars})
        fd = FakeFundamentals({})
        result = select(dt, ["UNKNOWN"], md, fd, sec_map={})
        assert result[0].passes_m1 is False
        assert "SEC" in (result[0].fail_reason or "")

    def test_fails_no_bars(self) -> None:
        dt = date(2026, 2, 1)
        md = FakeMarketData({})
        fd = FakeFundamentals({})
        result = select(dt, ["GHOST"], md, fd)
        assert result[0].passes_m1 is False
        assert "No recent bars" in (result[0].fail_reason or "")

    def test_all_symbols_get_reported(self) -> None:
        dt = date(2026, 2, 1)
        bars1 = _make_bars("AAPL", 30)
        bars2 = _make_bars("PENNY", 30, start_price=2.0)
        md = FakeMarketData({"AAPL": bars1, "PENNY": bars2})
        fd = FakeFundamentals({})
        result = select(dt, ["AAPL", "PENNY"], md, fd)
        assert len(result) == 2
        assert result[0].passes_m1 is True
        assert result[1].passes_m1 is False

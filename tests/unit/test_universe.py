from __future__ import annotations

from datetime import date, timedelta

from alpha_quant.domain.models import Bar
from alpha_quant.domain.universe import select


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
        result = select(dt, ["AAPL"], {"AAPL": bars}, {})
        assert len(result) == 1
        assert result[0].symbol == "AAPL"
        assert result[0].passes_m1 is True

    def test_fails_low_price(self) -> None:
        dt = date(2026, 2, 1)
        bars = _make_bars("PENNY", 30, start_price=2.0)
        result = select(dt, ["PENNY"], {"PENNY": bars}, {})
        assert result[0].passes_m1 is False
        assert "below" in (result[0].fail_reason or "")

    def test_fails_low_adv(self) -> None:
        dt = date(2026, 2, 1)
        bars = _make_bars("SMALL", 30, start_price=10.0, volume=1_000.0)
        result = select(dt, ["SMALL"], {"SMALL": bars}, {})
        assert result[0].passes_m1 is False
        assert "ADV" in (result[0].fail_reason or "")

    def test_fails_quarantined(self) -> None:
        dt = date(2026, 2, 1)
        bars = _make_bars("BAD", 30)
        result = select(dt, ["BAD"], {"BAD": bars}, {}, quarantined={"BAD"})
        assert result[0].passes_m1 is False
        assert "Quarantined" in (result[0].fail_reason or "")

    def test_fails_no_sec_map(self) -> None:
        dt = date(2026, 2, 1)
        bars = _make_bars("UNKNOWN", 30)
        result = select(dt, ["UNKNOWN"], {"UNKNOWN": bars}, {}, sec_map={})
        assert result[0].passes_m1 is False
        assert "SEC" in (result[0].fail_reason or "")

    def test_fails_no_bars(self) -> None:
        dt = date(2026, 2, 1)
        result = select(dt, ["GHOST"], {}, {})
        assert result[0].passes_m1 is False
        assert "No bars" in (result[0].fail_reason or "")

    def test_all_symbols_get_reported(self) -> None:
        dt = date(2026, 2, 1)
        bars1 = _make_bars("AAPL", 30)
        bars2 = _make_bars("PENNY", 30, start_price=2.0)
        result = select(dt, ["AAPL", "PENNY"], {"AAPL": bars1, "PENNY": bars2}, {})
        assert len(result) == 2
        assert result[0].passes_m1 is True
        assert result[1].passes_m1 is False

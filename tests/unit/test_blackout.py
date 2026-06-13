"""Unit tests for M7 earnings blackout (alpha_quant.domain.blackout)."""

from datetime import date

from alpha_quant.domain.blackout import check
from alpha_quant.domain.models import EarningsEntry


def _earnings(symbol: str, dt: date) -> EarningsEntry:
    return EarningsEntry(symbol=symbol, date=dt)


class TestCheck:
    def test_pass_when_no_earnings(self) -> None:
        result = check("AAPL", date(2026, 6, 11), [])
        assert result == "PASS"

    def test_block_3_trading_days_before(self) -> None:
        result = check(
            "AAPL",
            date(2026, 6, 22),
            [_earnings("AAPL", date(2026, 6, 25))],
        )
        assert result == "BLOCK"

    def test_pass_on_earnings_day(self) -> None:
        result = check(
            "AAPL",
            date(2026, 6, 25),
            [_earnings("AAPL", date(2026, 6, 25))],
        )
        assert result == "PASS"

    def test_block_2_trading_days_before(self) -> None:
        result = check(
            "AAPL",
            date(2026, 6, 23),
            [_earnings("AAPL", date(2026, 6, 25))],
        )
        assert result == "BLOCK"

    def test_block_1_trading_day_before(self) -> None:
        result = check(
            "AAPL",
            date(2026, 6, 24),
            [_earnings("AAPL", date(2026, 6, 25))],
        )
        assert result == "BLOCK"

    def test_block_4_trading_days_before(self) -> None:
        result = check(
            "AAPL",
            date(2026, 6, 19),
            [_earnings("AAPL", date(2026, 6, 25))],
        )
        assert result == "PASS"

    def test_weekend_handling(self) -> None:
        earnings_date = date(2026, 7, 1)
        friday = date(2026, 6, 26)
        result = check("AAPL", friday, [_earnings("AAPL", earnings_date)])
        assert result == "BLOCK"

    def test_case_insensitive_symbol(self) -> None:
        result = check(
            "aapl",
            date(2026, 6, 22),
            [_earnings("AAPL", date(2026, 6, 25))],
        )
        assert result == "BLOCK"

    def test_ignores_other_symbols(self) -> None:
        result = check(
            "AAPL",
            date(2026, 6, 22),
            [_earnings("MSFT", date(2026, 6, 25))],
        )
        assert result == "PASS"

    def test_uses_soonest_earnings(self) -> None:
        result = check(
            "AAPL",
            date(2026, 6, 20),
            [
                _earnings("AAPL", date(2026, 6, 30)),
                _earnings("AAPL", date(2026, 6, 23)),
            ],
        )
        assert result == "BLOCK"

    def test_custom_window_days(self) -> None:
        result = check(
            "AAPL",
            date(2026, 6, 19),
            [_earnings("AAPL", date(2026, 6, 25))],
            window_days=4,
        )
        assert result == "BLOCK"

    def test_skips_holiday_christmas(self) -> None:
        earnings_date = date(2025, 12, 26)
        monday_before = date(2025, 12, 22)
        result = check(
            "AAPL", monday_before, [_earnings("AAPL", earnings_date)]
        )
        assert result == "BLOCK"

    def test_does_not_overcount_holiday_week(self) -> None:
        earnings_date = date(2025, 12, 26)
        sunday_before = date(2025, 12, 21)
        result = check(
            "AAPL", sunday_before, [_earnings("AAPL", earnings_date)]
        )
        assert result == "PASS"

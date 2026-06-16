"""Unit tests for M7 earnings blackout (domain.blackout)."""

from datetime import date

from domain.blackout import check
from tests.conftest import make_earnings


class TestCheck:
    def test_pass_when_no_earnings(self) -> None:
        result = check("AAPL", date(2026, 6, 11), [])
        assert result == "PASS"

    def test_block_3_trading_days_before(self) -> None:
        result = check(
            "AAPL",
            date(2026, 6, 22),
            [make_earnings("AAPL", date(2026, 6, 25))],
        )
        assert result == "BLOCK"

    def test_pass_on_earnings_day(self) -> None:
        result = check(
            "AAPL",
            date(2026, 6, 25),
            [make_earnings("AAPL", date(2026, 6, 25))],
        )
        assert result == "PASS"

    def test_block_2_trading_days_before(self) -> None:
        result = check(
            "AAPL",
            date(2026, 6, 23),
            [make_earnings("AAPL", date(2026, 6, 25))],
        )
        assert result == "BLOCK"

    def test_block_1_trading_day_before(self) -> None:
        result = check(
            "AAPL",
            date(2026, 6, 24),
            [make_earnings("AAPL", date(2026, 6, 25))],
        )
        assert result == "BLOCK"

    def test_block_4_trading_days_before(self) -> None:
        result = check(
            "AAPL",
            date(2026, 6, 19),
            [make_earnings("AAPL", date(2026, 6, 25))],
        )
        assert result == "PASS"

    def test_weekend_handling(self) -> None:
        earnings_date = date(2026, 7, 1)
        friday = date(2026, 6, 26)
        result = check("AAPL", friday, [make_earnings("AAPL", earnings_date)])
        assert result == "BLOCK"

    def test_case_insensitive_symbol(self) -> None:
        result = check(
            "aapl",
            date(2026, 6, 22),
            [make_earnings("AAPL", date(2026, 6, 25))],
        )
        assert result == "BLOCK"

    def test_ignores_other_symbols(self) -> None:
        result = check(
            "AAPL",
            date(2026, 6, 22),
            [make_earnings("MSFT", date(2026, 6, 25))],
        )
        assert result == "PASS"

    def test_uses_soonest_earnings(self) -> None:
        result = check(
            "AAPL",
            date(2026, 6, 20),
            [
                make_earnings("AAPL", date(2026, 6, 30)),
                make_earnings("AAPL", date(2026, 6, 23)),
            ],
        )
        assert result == "BLOCK"

    def test_custom_window_days(self) -> None:
        result = check(
            "AAPL",
            date(2026, 6, 19),
            [make_earnings("AAPL", date(2026, 6, 25))],
            window_days=4,
        )
        assert result == "BLOCK"

    def test_skips_holiday_christmas(self) -> None:
        earnings_date = date(2025, 12, 26)
        monday_before = date(2025, 12, 22)
        result = check("AAPL", monday_before, [make_earnings("AAPL", earnings_date)])
        assert result == "BLOCK"

    def test_does_not_overcount_holiday_week(self) -> None:
        earnings_date = date(2025, 12, 26)
        sunday_before = date(2025, 12, 21)
        result = check("AAPL", sunday_before, [make_earnings("AAPL", earnings_date)])
        assert result == "PASS"

    def test_ignores_past_earnings_when_future_exists(self) -> None:
        result = check(
            "AAPL",
            date(2026, 6, 16),
            [
                make_earnings("AAPL", date(2026, 3, 15)),
                make_earnings("AAPL", date(2026, 6, 22)),
            ],
        )
        assert result == "BLOCK"

    def test_only_past_earnings_returns_pass(self) -> None:
        result = check(
            "AAPL",
            date(2026, 6, 16),
            [make_earnings("AAPL", date(2026, 3, 15))],
        )
        assert result == "PASS"

    def test_mixed_past_and_future_uses_next_future(self) -> None:
        result = check(
            "AAPL",
            date(2026, 6, 16),
            [
                make_earnings("AAPL", date(2026, 3, 15)),
                make_earnings("AAPL", date(2026, 6, 22)),
                make_earnings("AAPL", date(2026, 9, 15)),
            ],
        )
        assert result == "BLOCK"

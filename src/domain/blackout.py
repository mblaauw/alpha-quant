"""Blackout period detection for earnings and events."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from domain.calendar import is_market_day
from domain.models import EarningsEntry

BlackoutVerdict = Literal["BLOCK", "PASS"]


def check(
    symbol: str,
    target_date: date,
    earnings_calendar: list[EarningsEntry],
    window_days: int = 3,
) -> BlackoutVerdict:
    report = _next_earnings(symbol, earnings_calendar, target_date)
    if report is None:
        return "PASS"

    blackout_start = _trading_days_before(report, window_days)
    if blackout_start <= target_date <= report:
        return "BLOCK"

    return "PASS"


def _next_earnings(symbol: str, calendar: list[EarningsEntry], after: date) -> date | None:
    upcoming = [e.date for e in calendar if e.symbol.upper() == symbol.upper() and e.date > after]
    if not upcoming:
        return None
    return min(upcoming)


def _trading_days_before(dt: date, n: int) -> date:
    result = dt
    while n > 0:
        result -= timedelta(days=1)
        if is_market_day(result):
            n -= 1
    return result

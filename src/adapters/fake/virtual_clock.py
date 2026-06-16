from datetime import UTC, date, datetime, timedelta
from typing import override

from domain.calendar import is_market_day, prev_market_day
from ports.clock import Clock


class VirtualClock(Clock):
    def __init__(self, start_date: date) -> None:
        self._current = datetime(start_date.year, start_date.month, start_date.day, tzinfo=UTC)

    @override
    def now(self) -> datetime:
        return self._current

    @override
    def today(self) -> date:
        return self._current.date()

    @override
    def market_date(self) -> date:
        return prev_market_day(self._current.date())

    def advance(self) -> None:
        self._current += timedelta(days=1)
        while not is_market_day(self._current.date()):
            self._current += timedelta(days=1)

    def set_to(self, dt: datetime) -> None:
        self._current = dt

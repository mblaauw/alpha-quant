from datetime import UTC, date, datetime
from typing import override

from domain.calendar import prev_market_day
from ports.clock import Clock


class SystemClock(Clock):
    @override
    def now(self) -> datetime:
        return datetime.now(UTC)

    @override
    def today(self) -> date:
        return self.now().date()

    @override
    def market_date(self) -> date:
        return prev_market_day(self.today())

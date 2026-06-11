from datetime import UTC, date, datetime

from alpha_quant.app.calendar import prev_market_day
from alpha_quant.ports.clock import Clock


class SystemClock(Clock):
    def now(self) -> datetime:
        return datetime.now(UTC)

    def today(self) -> date:
        return self.now().date()

    def market_date(self) -> date:
        return prev_market_day(self.today())

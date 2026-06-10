from datetime import date, datetime, timedelta

from alpha_quant.ports.clock import Clock


class FakeClock(Clock):
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def today(self) -> date:
        return self._now.date()

    def market_date(self) -> date:
        return self._now.date()

    def advance(self, **kwargs: float) -> None:
        self._now += timedelta(**kwargs)

    def set_to(self, dt: datetime) -> None:
        self._now = dt

from abc import ABC, abstractmethod
from datetime import date

from domain.models import EarningsEntry, FundamentalsSnapshot


class Fundamentals(ABC):
    @abstractmethod
    def snapshot(self, symbol: str) -> FundamentalsSnapshot: ...

    @abstractmethod
    def earnings_calendar(self, start: date, end: date) -> list[EarningsEntry]: ...

from abc import ABC, abstractmethod

from alpha_quant.domain.models import EarningsEntry, FundamentalsSnapshot


class Fundamentals(ABC):
    @abstractmethod
    async def snapshot(self, symbol: str) -> FundamentalsSnapshot: ...

    @abstractmethod
    async def earnings_calendar(self, start: str, end: str) -> list[EarningsEntry]: ...

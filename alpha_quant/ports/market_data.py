from abc import ABC, abstractmethod
from datetime import date

from alpha_quant.domain.models import Bar, Quote, TradingDay


class MarketData(ABC):
    @abstractmethod
    async def daily_bars(self, symbol: str, start: date, end: date) -> list[Bar]: ...

    @abstractmethod
    async def latest_quote(self, symbol: str) -> Quote: ...

    @abstractmethod
    async def trading_calendar(self, start: date, end: date) -> list[TradingDay]: ...

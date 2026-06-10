from datetime import date
from typing import Protocol, runtime_checkable


@runtime_checkable
class MarketData(Protocol):
    async def bars(self, symbol: str, start: date, end: date) -> list[dict]: ...

    async def quote(self, symbol: str) -> dict: ...

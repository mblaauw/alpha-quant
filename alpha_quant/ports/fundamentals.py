from typing import Protocol, runtime_checkable


@runtime_checkable
class Fundamentals(Protocol):
    async def fundamentals(self, symbol: str) -> dict: ...

    async def earnings_calendar(self, start: str, end: str) -> list[dict]: ...

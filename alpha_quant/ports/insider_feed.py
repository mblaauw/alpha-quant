from typing import Protocol, runtime_checkable


@runtime_checkable
class InsiderFeed(Protocol):
    async def insider_trades(self, symbol: str) -> list[dict]: ...

    async def cluster_signals(self, symbol: str) -> list[dict]: ...

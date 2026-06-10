from typing import Protocol, runtime_checkable


@runtime_checkable
class SentimentFeed(Protocol):
    async def sentiment(self, symbol: str) -> dict: ...

    async def trending(self, limit: int = 20) -> list[dict]: ...

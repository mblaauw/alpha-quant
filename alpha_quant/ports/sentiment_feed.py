from abc import ABC, abstractmethod

from alpha_quant.domain.models import MentionCount, SentimentBaseline


class SentimentFeed(ABC):
    @abstractmethod
    async def mention_counts(self, symbol: str, days: int = 30) -> list[MentionCount]: ...

    @abstractmethod
    async def baseline(self, symbol: str) -> SentimentBaseline: ...

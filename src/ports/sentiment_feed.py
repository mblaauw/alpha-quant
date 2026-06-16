from abc import ABC, abstractmethod

from domain.models import MentionCount, SentimentBaseline


class SentimentFeed(ABC):
    @abstractmethod
    def mention_counts(self, symbol: str, days: int = 30) -> list[MentionCount]: ...

    @abstractmethod
    def baseline(self, symbol: str) -> SentimentBaseline: ...

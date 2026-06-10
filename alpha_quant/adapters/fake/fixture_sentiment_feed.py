from alpha_quant.domain.models import MentionCount, SentimentBaseline
from alpha_quant.ports.sentiment_feed import SentimentFeed


class FixtureSentimentFeed(SentimentFeed):
    def __init__(
        self,
        baselines: dict[str, SentimentBaseline] | None = None,
    ) -> None:
        self._baselines: dict[str, SentimentBaseline] = baselines or {}
        self._mentions: dict[str, list[MentionCount]] = {}

    def seed_baseline(self, symbol: str, baseline: SentimentBaseline) -> None:
        self._baselines[symbol] = baseline

    def seed_mentions(self, symbol: str, mentions: list[MentionCount]) -> None:
        self._mentions[symbol] = mentions

    async def mention_counts(self, symbol: str, days: int = 30) -> list[MentionCount]:
        if symbol not in self._mentions:
            msg = f"No fixture mentions for symbol: {symbol}"
            raise ValueError(msg)
        return self._mentions[symbol][-days:]

    async def baseline(self, symbol: str) -> SentimentBaseline:
        if symbol not in self._baselines:
            msg = f"No fixture sentiment baseline for symbol: {symbol}"
            raise ValueError(msg)
        return self._baselines[symbol]

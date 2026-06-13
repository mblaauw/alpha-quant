from __future__ import annotations

from datetime import date
from pathlib import Path
from statistics import mean, stdev
from typing import override

import pyarrow.parquet as pq

from alpha_quant.domain.models import MentionCount, SentimentBaseline
from alpha_quant.ports.sentiment_feed import SentimentFeed


class FixtureSentimentFeed(SentimentFeed):
    def __init__(self, fixture_path: Path) -> None:
        self._mentions_dir = fixture_path / "mentions"

    @override
    def mention_counts(self, symbol: str, days: int = 30) -> list[MentionCount]:
        path = self._mentions_dir / f"{symbol}.parquet"
        if not path.exists():
            return []
        table = pq.read_table(path)
        counts: list[MentionCount] = []
        for i in range(table.num_rows):
            row = {col: table.column(col)[i].as_py() for col in table.column_names}
            counts.append(
                MentionCount(
                    symbol=row.get("symbol", symbol),
                    mention_date=row.get("date", date.today()),
                    source=row.get("source", "fixture"),
                    count=int(row.get("count", 0)),
                )
            )
        return counts

    @override
    def baseline(self, symbol: str) -> SentimentBaseline:
        counts = self.mention_counts(symbol)
        values = [c.count for c in counts]
        if len(values) < 2:
            return SentimentBaseline(
                symbol=symbol,
                mean_mentions=float(sum(values)) if values else 0.0,
                std_mentions=0.0,
            )
        avg = mean(values)
        sd = stdev(values)
        current = values[-1]
        z = (current - avg) / sd if sd > 0 else 0.0
        return SentimentBaseline(
            symbol=symbol,
            mean_mentions=avg,
            std_mentions=sd,
            z_score=round(z, 4),
        )

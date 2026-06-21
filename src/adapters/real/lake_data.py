from __future__ import annotations

from datetime import UTC, date, datetime, time
from statistics import mean, stdev
from typing import override

from domain.models import (
    Bar,
    EarningsEntry,
    FundamentalsSnapshot,
    InsiderCluster,
    InsiderTransaction,
    MentionCount,
    Quote,
    SentimentBaseline,
    TradingDay,
)
from ports.clock import Clock
from ports.fundamentals import Fundamentals
from ports.insider_feed import InsiderFeed
from ports.lake import LakeGateway
from ports.market_data import MarketData
from ports.sentiment_feed import SentimentFeed


class LakeMarketData(MarketData):
    def __init__(self, lake: LakeGateway, clock: Clock, price_mode: str = "split_adjusted") -> None:
        self._lake = lake
        self._clock = clock
        self._price_mode = price_mode

    @override
    def daily_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        return self._lake.bars(
            symbol,
            start,
            end,
            as_of=self._clock.now(),
            price_mode=self._price_mode,
        )

    @override
    def latest_quote(self, symbol: str) -> Quote:
        as_of = self._clock.now()
        bar = self._lake.latest_bar(symbol, as_of=as_of)
        if bar is None:
            return Quote(symbol=symbol, timestamp=as_of)
        ts = datetime.combine(bar.date, time.max, tzinfo=UTC)
        return Quote(symbol=symbol, timestamp=ts, price=bar.close, volume=bar.volume)

    @override
    def trading_calendar(self, start: date, end: date) -> list[TradingDay]:
        return self._lake.trading_calendar(start, end)


class LakeFundamentals(Fundamentals):
    def __init__(self, lake: LakeGateway, clock: Clock) -> None:
        self._lake = lake
        self._clock = clock

    @override
    def snapshot(self, symbol: str) -> FundamentalsSnapshot:
        snap = self._lake.fundamentals(symbol, as_of=self._clock.now())
        if snap is None:
            return FundamentalsSnapshot(symbol=symbol, as_of_date=self._clock.today())
        return snap

    @override
    def earnings_calendar(self, start: date, end: date) -> list[EarningsEntry]:
        return self._lake.earnings_calendar(start, end, as_of=self._clock.now())


class LakeInsiderFeed(InsiderFeed):
    def __init__(self, lake: LakeGateway, clock: Clock) -> None:
        self._lake = lake
        self._clock = clock

    @override
    def cluster_transactions(self, symbol: str) -> list[InsiderTransaction]:
        return self._lake.insider_transactions(symbol, as_of=self._clock.now())

    @override
    def recent_clusters(self, symbol: str) -> list[InsiderCluster]:
        txns = self.cluster_transactions(symbol)
        if not txns:
            return []
        dated = [txn for txn in txns if txn.filing_date is not None]
        if not dated:
            return []
        cluster_date = max(txn.filing_date for txn in dated if txn.filing_date is not None)
        net_shares = sum(
            txn.shares_traded
            if txn.transaction_type.lower().startswith(("buy", "p"))
            else -txn.shares_traded
            for txn in txns
        )
        prices = [txn.price for txn in txns if txn.price is not None]
        return [
            InsiderCluster(
                symbol=symbol,
                cluster_date=cluster_date,
                num_transactions=len(txns),
                net_shares=net_shares,
                avg_price=mean(prices) if prices else None,
            )
        ]


class LakeSentimentFeed(SentimentFeed):
    def __init__(self, lake: LakeGateway, clock: Clock) -> None:
        self._lake = lake
        self._clock = clock

    @override
    def mention_counts(self, symbol: str, days: int = 30) -> list[MentionCount]:
        return self._lake.mention_counts(symbol, days=days, as_of=self._clock.now())

    @override
    def baseline(self, symbol: str) -> SentimentBaseline:
        counts = self.mention_counts(symbol)
        values = [count.count for count in counts]
        if not values:
            return SentimentBaseline(symbol=symbol, mean_mentions=0.0, std_mentions=0.0)
        if len(values) == 1:
            return SentimentBaseline(
                symbol=symbol,
                mean_mentions=float(values[0]),
                std_mentions=0.0,
                z_score=0.0,
            )
        avg = mean(values)
        std = stdev(values)
        z_score = (values[-1] - avg) / std if std > 0 else 0.0
        return SentimentBaseline(
            symbol=symbol,
            mean_mentions=avg,
            std_mentions=std,
            z_score=round(z_score, 4),
        )

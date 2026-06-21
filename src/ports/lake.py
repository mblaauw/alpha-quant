from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime

from domain.models import (
    Bar,
    EarningsEntry,
    FundamentalsSnapshot,
    InsiderTransaction,
    MentionCount,
    TradingDay,
)


class LakeGateway(ABC):
    """Point-in-time data access boundary to Alpha-Lake."""

    @abstractmethod
    def bars(
        self,
        symbol: str,
        start: date,
        end: date,
        as_of: datetime,
        price_mode: str = "split_adjusted",
    ) -> list[Bar]: ...

    @abstractmethod
    def latest_bar(self, symbol: str, as_of: datetime) -> Bar | None: ...

    @abstractmethod
    def trading_calendar(self, start: date, end: date) -> list[TradingDay]: ...

    @abstractmethod
    def fundamentals(self, symbol: str, as_of: datetime) -> FundamentalsSnapshot | None: ...

    @abstractmethod
    def earnings_calendar(self, start: date, end: date, as_of: datetime) -> list[EarningsEntry]: ...

    @abstractmethod
    def insider_transactions(self, symbol: str, as_of: datetime) -> list[InsiderTransaction]: ...

    @abstractmethod
    def mention_counts(self, symbol: str, days: int, as_of: datetime) -> list[MentionCount]: ...

    @abstractmethod
    def dataset_health(self) -> dict[str, object]: ...

    @abstractmethod
    def pin_snapshot(self, snapshot_id: str | None) -> None: ...

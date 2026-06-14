from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from datetime import date, datetime
from typing import Self

from alpha_quant.domain.events import DomainEvent
from alpha_quant.domain.journal import JournalEntry
from alpha_quant.domain.models import (
    Bar,
    CorporateAction,
    Decision,
    EarningsEntry,
    Fill,
    FundamentalsSnapshot,
    IndicatorState,
    InsiderTransaction,
    MentionCount,
    Order,
    PortfolioSnapshot,
    Position,
)
from alpha_quant.domain.reporting import ReportEntry


class BarStore(ABC):
    """Bar data read/write interface."""

    @abstractmethod
    def save_bars(self, symbol: str, bars: list[Bar]) -> None: ...

    @abstractmethod
    def load_bars(self, symbol: str, start: date, end: date) -> list[Bar]: ...

    @abstractmethod
    def save_corp_actions(self, symbol: str, actions: list[CorporateAction]) -> None: ...

    @abstractmethod
    def load_corp_actions(self, symbol: str) -> list[CorporateAction]: ...

    @abstractmethod
    def save_earnings(self, symbol: str, entries: list[EarningsEntry]) -> None: ...

    @abstractmethod
    def load_earnings(self, symbol: str) -> list[EarningsEntry]: ...

    @abstractmethod
    def load_fundamentals(self, symbol: str) -> list[FundamentalsSnapshot]: ...

    @abstractmethod
    def load_insider_transactions(self, symbol: str) -> list[InsiderTransaction]: ...

    @abstractmethod
    def load_mentions(self, symbol: str) -> list[MentionCount]: ...


class DecisionStore(ABC):
    """Decision read/write interface."""

    @abstractmethod
    def save_decision(self, decision: Decision) -> None: ...

    @abstractmethod
    def load_decisions(self, symbol: str, since: date) -> list[Decision]: ...


class OrderStore(ABC):
    """Order and fill read/write interface."""

    @abstractmethod
    def save_order(self, order: Order) -> None: ...

    @abstractmethod
    def load_order(self, order_id: str) -> Order | None: ...

    @abstractmethod
    def save_fill(self, fill: Fill) -> None: ...

    @abstractmethod
    def load_fills(self, order_id: str) -> list[Fill]: ...


class PositionStore(ABC):
    """Position and portfolio read/write interface."""

    @abstractmethod
    def save_position(self, position: Position) -> None: ...

    @abstractmethod
    def load_positions(self) -> list[Position]: ...

    @abstractmethod
    def save_portfolio_snapshot(self, snapshot: PortfolioSnapshot) -> None: ...

    @abstractmethod
    def load_latest_portfolio_snapshot(self, book: str = "PAPER") -> PortfolioSnapshot | None: ...

    @abstractmethod
    def load_portfolio_snapshots(
        self, book: str = "PAPER", limit: int = 500
    ) -> list[PortfolioSnapshot]: ...


class EventStore(ABC):
    """Domain event read/write interface."""

    @abstractmethod
    def save_event(self, event: DomainEvent) -> None: ...

    @abstractmethod
    def load_events(
        self,
        event_type: str | None = None,
        since: datetime | None = None,
    ) -> list[DomainEvent]: ...


class IndicatorStore(ABC):
    """Indicator state read/write interface."""

    @abstractmethod
    def save_indicator_state(self, state: IndicatorState) -> None: ...

    @abstractmethod
    def load_indicator_state(self, symbol: str, dt: date) -> IndicatorState | None: ...


class JournalStore(ABC):
    """Journal and report read/write interface."""

    @abstractmethod
    def save_journal(self, entry: JournalEntry) -> None: ...

    @abstractmethod
    def load_journal(self, dt: date) -> JournalEntry | None: ...

    @abstractmethod
    def save_report(self, report: ReportEntry) -> None: ...

    @abstractmethod
    def load_report(self, dt: date, report_type: str) -> ReportEntry | None: ...


class AdminStore(ABC):
    """Admin operations: quarantine, runs, lifecycle."""

    @abstractmethod
    def transaction(self) -> AbstractContextManager[Self]: ...

    @abstractmethod
    def add_quarantine(self, symbol: str, reason: str, severity: str = "QUARANTINE") -> None: ...

    @abstractmethod
    def list_quarantine(self, cleared: bool = False) -> list[dict[str, object]]: ...

    @abstractmethod
    def clear_quarantine(self, symbol: str) -> None: ...

    @abstractmethod
    def register_run(self, run_type: str, config_hash: str, fixture_version: str = "") -> str: ...

    @abstractmethod
    def complete_run(
        self, run_id: str, status: str = "completed", manifest_hash: str = ""
    ) -> None: ...

    @abstractmethod
    def list_runs(self, since_date: date | None = None) -> list[dict[str, object]]: ...

    @abstractmethod
    def close(self) -> None: ...


class Store(
    BarStore,
    DecisionStore,
    OrderStore,
    PositionStore,
    EventStore,
    IndicatorStore,
    JournalStore,
    AdminStore,
):
    """Composite store interface combining all role-specific interfaces."""

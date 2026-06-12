from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import date, datetime
from typing import Self, override

from alpha_quant.domain.events import DomainEvent
from alpha_quant.domain.journal import JournalEntry
from alpha_quant.domain.models import (
    Bar,
    CorporateAction,
    Decision,
    EarningsEntry,
    Fill,
    IndicatorState,
    Order,
    PortfolioSnapshot,
    Position,
)
from alpha_quant.domain.reporting import ReportEntry
from alpha_quant.ports.store import Store


class FixtureStore(Store):
    def __init__(self) -> None:
        self._bars: dict[tuple[str, date], list[Bar]] = {}
        self._orders: dict[str, Order] = {}
        self._fills: dict[str, list[Fill]] = {}
        self._positions: list[Position] = []
        self._events: list[DomainEvent] = []
        self._portfolio_snapshots: list[PortfolioSnapshot] = []
        self._journals: dict[date, JournalEntry] = {}
        self._reports: dict[tuple[date, str], ReportEntry] = {}

    @contextmanager
    def transaction(self) -> Generator[Self]:
        yield self

    @override
    def save_bars(self, symbol: str, bars: list[Bar]) -> None:
        self._bars[(symbol, bars[0].date if bars else date.today())] = bars

    @override
    def load_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        return [
            b
            for (sym, _), bars in self._bars.items()
            if sym == symbol
            for b in bars
            if start <= b.date <= end
        ]

    @override
    def save_decision(self, decision: Decision) -> None:
        pass

    @override
    def load_decisions(self, symbol: str, since: date) -> list[Decision]:
        return []

    @override
    def save_order(self, order: Order) -> None:
        self._orders[order.order_id] = order

    @override
    def load_order(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    @override
    def save_fill(self, fill: Fill) -> None:
        self._fills.setdefault(fill.order_id, []).append(fill)

    @override
    def load_fills(self, order_id: str) -> list[Fill]:
        return self._fills.get(order_id, [])

    @override
    def save_position(self, position: Position) -> None:
        existing = [i for i, p in enumerate(self._positions) if p.symbol == position.symbol]
        if existing:
            self._positions[existing[0]] = position
        else:
            self._positions.append(position)

    @override
    def load_positions(self) -> list[Position]:
        return list(self._positions)

    @override
    def save_event(self, event: DomainEvent) -> None:
        self._events.append(event)

    @override
    def load_events(
        self,
        event_type: str | None = None,
        since: datetime | None = None,
    ) -> list[DomainEvent]:
        result = list(self._events)
        if event_type:
            result = [e for e in result if e.event_type == event_type]
        if since:
            result = [e for e in result if e.timestamp >= since]
        return result

    @override
    def save_indicator_state(self, state: IndicatorState) -> None:
        pass

    @override
    def load_indicator_state(self, symbol: str, dt: date) -> IndicatorState | None:
        return None

    @override
    def save_corp_actions(self, symbol: str, actions: list[CorporateAction]) -> None:
        pass

    @override
    def load_corp_actions(self, symbol: str) -> list[CorporateAction]:
        return []

    @override
    def save_earnings(self, symbol: str, entries: list[EarningsEntry]) -> None:
        pass

    @override
    def load_earnings(self, symbol: str) -> list[EarningsEntry]:
        return []

    @override
    def save_portfolio_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        self._portfolio_snapshots.append(snapshot)

    @override
    def load_latest_portfolio_snapshot(self) -> PortfolioSnapshot | None:
        if not self._portfolio_snapshots:
            return None
        return max(self._portfolio_snapshots, key=lambda s: s.date)

    @override
    def save_journal(self, entry: JournalEntry) -> None:
        self._journals[entry.date] = entry

    @override
    def load_journal(self, dt: date) -> JournalEntry | None:
        return self._journals.get(dt)

    @override
    def save_report(self, report: ReportEntry) -> None:
        self._reports[(report.date, report.report_type)] = report

    @override
    def load_report(self, dt: date, report_type: str) -> ReportEntry | None:
        return self._reports.get((dt, report_type))

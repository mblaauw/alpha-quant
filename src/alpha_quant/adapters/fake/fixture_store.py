from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import date, datetime
from typing import Self, override

from alpha_quant.domain.events import DomainEvent
from alpha_quant.domain.journal import JournalEntry
from alpha_quant.domain.models import (
    Decision,
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
        self._orders: dict[str, Order] = {}
        self._fills: dict[str, list[Fill]] = {}
        self._positions: list[Position] = []
        self._events: list[DomainEvent] = []
        self._portfolio_snapshots: list[PortfolioSnapshot] = []
        self._journals: dict[date, JournalEntry] = {}
        self._reports: dict[tuple[date, str], ReportEntry] = {}
        self._decisions: dict[str, list[Decision]] = {}
        self._indicator_states: dict[tuple[str, date], IndicatorState] = {}
        self._quarantine: list[dict[str, object]] = []
        self._runs: dict[str, str] = {}

    @contextmanager
    def transaction(self) -> Generator[Self]:
        yield self

    @override
    def save_decision(self, decision: Decision) -> None:
        self._decisions.setdefault(decision.symbol, []).append(decision)

    @override
    def load_decisions(self, symbol: str, since: date) -> list[Decision]:
        return [d for d in self._decisions.get(symbol, []) if d.date >= since]

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
        self._indicator_states[(state.symbol, state.date)] = state

    @override
    def load_indicator_state(self, symbol: str, dt: date) -> IndicatorState | None:
        return self._indicator_states.get((symbol, dt))

    @override
    def save_portfolio_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        self._portfolio_snapshots.append(snapshot)

    @override
    def load_latest_portfolio_snapshot(self, book: str = "PAPER") -> PortfolioSnapshot | None:
        matching = [s for s in self._portfolio_snapshots if s.book == book]
        if not matching:
            return None
        return max(matching, key=lambda s: s.date)

    @override
    def load_portfolio_snapshots(
        self, book: str = "PAPER", limit: int = 500
    ) -> list[PortfolioSnapshot]:
        matching = [s for s in self._portfolio_snapshots if s.book == book]
        return sorted(matching, key=lambda s: s.date)[:limit]

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

    @override
    def add_quarantine(self, symbol: str, reason: str, severity: str = "QUARANTINE") -> None:
        self._quarantine.append(
            {
                "symbol": symbol,
                "reason": reason,
                "severity": severity,
                "quarantined_date": date.today(),
                "cleared_date": None,
            }
        )

    @override
    def list_quarantine(self, cleared: bool = False) -> list[dict[str, object]]:
        if cleared:
            return [q for q in self._quarantine if q.get("cleared_date") is not None]
        return [q for q in self._quarantine if q.get("cleared_date") is None]

    @override
    def clear_quarantine(self, symbol: str) -> None:
        for q in self._quarantine:
            if q["symbol"] == symbol:
                q["cleared_date"] = date.today()

    _run_counter: int = 0

    @override
    def register_run(self, run_type: str, config_hash: str, fixture_version: str = "") -> str:
        FixtureStore._run_counter += 1
        run_id = f"fixture-run-{FixtureStore._run_counter}"
        self._runs[run_id] = run_type
        return run_id

    @override
    def complete_run(self, run_id: str, status: str = "completed", manifest_hash: str = "") -> None:
        if run_id in self._runs:
            self._runs[run_id] = status

    @override
    def list_runs(self, since_date: date | None = None) -> list[dict[str, object]]:
        return [{"run_id": rid, "run_type": rt} for rid, rt in self._runs.items()]

    @override
    def close(self) -> None:
        pass

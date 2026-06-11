from __future__ import annotations

from datetime import date, datetime

from alpha_quant.domain.events import DomainEvent
from alpha_quant.domain.models import (
    Bar,
    Decision,
    Fill,
    IndicatorState,
    Order,
    Position,
)
from alpha_quant.ports.store import Store


class FixtureStore(Store):
    def __init__(self) -> None:
        self._bars: dict[tuple[str, date], list[Bar]] = {}

    def save_bars(self, symbol: str, bars: list[Bar]) -> None:
        self._bars[(symbol, bars[0].date if bars else date.today())] = bars

    def load_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        return [
            b
            for (sym, _), bars in self._bars.items()
            if sym == symbol
            for b in bars
            if start <= b.date <= end
        ]

    def save_decision(self, decision: Decision) -> None:
        pass

    def load_decisions(self, symbol: str, since: date) -> list[Decision]:
        return []

    def save_order(self, order: Order) -> None:
        pass

    def load_order(self, order_id: str) -> Order | None:
        return None

    def save_fill(self, fill: Fill) -> None:
        pass

    def load_fills(self, order_id: str) -> list[Fill]:
        return []

    def save_position(self, position: Position) -> None:
        pass

    def load_positions(self) -> list[Position]:
        return []

    def save_event(self, event: DomainEvent) -> None:
        pass

    def load_events(
        self,
        event_type: str | None = None,
        since: datetime | None = None,
    ) -> list[DomainEvent]:
        return []

    def save_indicator_state(self, state: IndicatorState) -> None:
        pass

    def load_indicator_state(self, symbol: str, dt: date) -> IndicatorState | None:
        return None

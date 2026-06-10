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


class FakeStore(Store):
    def __init__(self) -> None:
        self._bars: dict[str, list[Bar]] = {}
        self._decisions: list[Decision] = []
        self._orders: dict[str, Order] = {}
        self._fills: list[Fill] = []
        self._positions: list[Position] = []
        self._events: list[DomainEvent] = []
        self._indicator_states: dict[tuple[str, date], IndicatorState] = {}

    async def save_bars(self, symbol: str, bars: list[Bar]) -> None:
        self._bars.setdefault(symbol, []).extend(bars)

    async def load_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        return [b for b in self._bars.get(symbol, []) if start <= b.date <= end]

    async def save_decision(self, decision: Decision) -> None:
        self._decisions.append(decision)

    async def load_decisions(self, symbol: str, since: date) -> list[Decision]:
        return [d for d in self._decisions if d.symbol == symbol and d.date >= since]

    async def save_order(self, order: Order) -> None:
        self._orders[order.order_id] = order

    async def load_order(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    async def save_fill(self, fill: Fill) -> None:
        self._fills.append(fill)

    async def load_fills(self, order_id: str) -> list[Fill]:
        return [f for f in self._fills if f.order_id == order_id]

    async def save_position(self, position: Position) -> None:
        self._positions = [p for p in self._positions if p.symbol != position.symbol]
        self._positions.append(position)

    async def load_positions(self) -> list[Position]:
        return list(self._positions)

    async def save_event(self, event: DomainEvent) -> None:
        self._events.append(event)

    async def load_events(
        self,
        event_type: str | None = None,
        since: datetime | None = None,
    ) -> list[DomainEvent]:
        results: list[DomainEvent] = list(self._events)
        if event_type is not None:
            results = [e for e in results if getattr(e, "event_type", None) == event_type]
        if since is not None:
            results = [e for e in results if getattr(e, "occurred_at", datetime.min) >= since]
        return results

    async def save_indicator_state(self, state: IndicatorState) -> None:
        self._indicator_states[(state.symbol, state.date)] = state

    async def load_indicator_state(self, symbol: str, date: date) -> IndicatorState | None:
        return self._indicator_states.get((symbol, date))

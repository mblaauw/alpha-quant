from datetime import datetime

from alpha_quant.domain.models import Fill, Order, Position
from alpha_quant.ports.broker import Broker
from alpha_quant.ports.clock import Clock


class FakeBroker(Broker):
    def __init__(self, clock: Clock | None = None) -> None:
        self._clock = clock
        self._orders: dict[str, Order] = {}
        self._positions: list[Position] = []
        self._portfolio_value: dict = {
            "equity": 100_000.0,
            "cash": 100_000.0,
            "positions_value": 0.0,
            "return_pct": 0.0,
        }
        self._fill_log: list[Fill] = []
        self._next_order_id: int = 1

    def _now(self) -> datetime:
        if self._clock is not None:
            return self._clock.now()
        return datetime.fromisoformat("2026-01-01T00:00:00+00:00")

    def seed_positions(self, positions: list[Position]) -> None:
        self._positions = positions

    def seed_portfolio(self, portfolio: dict) -> None:
        self._portfolio_value.update(portfolio)

    async def submit_order(self, order: Order) -> Order:
        order_id = f"fake-{self._next_order_id}"
        self._next_order_id += 1
        now = self._now()
        filled = Order(
            order_id=order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
            limit_price=order.limit_price,
            status="filled",
            submitted_at=now,
            filled_at=now,
            filled_quantity=order.quantity,
            avg_fill_price=order.limit_price or 100.0,
        )
        self._orders[order_id] = filled
        fill = Fill(
            fill_id=f"fill-{order_id}",
            order_id=order_id,
            symbol=order.symbol,
            quantity=order.quantity,
            price=order.limit_price or 100.0,
            timestamp=now,
        )
        self._fill_log.append(fill)
        return filled

    async def cancel_order(self, order_id: str) -> bool:
        if order_id not in self._orders:
            return False
        existing = self._orders[order_id]
        self._orders[order_id] = Order(
            order_id=existing.order_id,
            symbol=existing.symbol,
            side=existing.side,
            quantity=existing.quantity,
            order_type=existing.order_type,
            limit_price=existing.limit_price,
            status="cancelled",
            submitted_at=existing.submitted_at,
            filled_at=existing.filled_at,
            filled_quantity=existing.filled_quantity,
            avg_fill_price=existing.avg_fill_price,
        )
        return True

    async def portfolio(self) -> dict:
        return dict(self._portfolio_value)

    async def positions(self) -> list[Position]:
        return list(self._positions)

    async def fills(self, since: str | None = None) -> list[Fill]:
        if since is None:
            return list(self._fill_log)
        since_dt = datetime.fromisoformat(since)
        return [f for f in self._fill_log if f.timestamp >= since_dt]

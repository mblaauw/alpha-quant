"""FakeBroker — in-memory order book for testing."""

import uuid
from datetime import UTC, datetime
from typing import override

from alpha_quant.domain.models import Fill, Order, Position
from alpha_quant.ports.broker import Broker


class FakeBroker(Broker):
    def __init__(self, initial_cash: float = 1_000_000.0) -> None:
        self._cash = initial_cash
        self._orders: dict[str, Order] = {}
        self._positions: dict[str, Position] = {}
        self._fills: list[Fill] = []

    @override
    def submit_order(self, order: Order) -> Order:
        filled = order.model_copy(
            update={
                "status": "filled",
                "order_id": order.order_id or uuid.uuid4().hex[:16],
                "fill_date": datetime.now(UTC).date(),
                "filled_quantity": order.quantity,
                "avg_fill_price": order.limit_price or 100.0,
            }
        )
        self._orders[filled.order_id] = filled
        fill = Fill(
            fill_id=uuid.uuid4().hex[:16],
            order_id=filled.order_id,
            symbol=order.symbol,
            quantity=order.quantity,
            price=filled.avg_fill_price or 0.0,
            timestamp=datetime.now(UTC),
        )
        self._fills.append(fill)
        cost = fill.quantity * fill.price
        self._cash -= cost
        existing = self._positions.get(order.symbol)
        if existing is not None:
            total_qty = existing.quantity + order.quantity
            avg = ((existing.avg_cost * existing.quantity) + cost) / total_qty
            self._positions[order.symbol] = existing.model_copy(
                update={
                    "quantity": total_qty,
                    "avg_cost": avg,
                    "market_value": total_qty * fill.price,
                }
            )
        else:
            self._positions[order.symbol] = Position(
                symbol=order.symbol,
                quantity=order.quantity,
                entry_price=fill.price,
                avg_cost=fill.price,
                current_price=fill.price,
                market_value=cost,
            )
        return filled

    @override
    def cancel_order(self, order_id: str) -> bool:
        order = self._orders.get(order_id)
        if order is None:
            return False
        self._orders[order_id] = order.model_copy(update={"status": "cancelled"})
        return True

    @override
    def portfolio(self) -> dict:
        total_mv = sum(p.market_value or 0 for p in self._positions.values())
        return {
            "cash": self._cash,
            "equity": self._cash + total_mv,
            "positions": len(self._positions),
        }

    @override
    def positions(self) -> list[Position]:
        return list(self._positions.values())

    @override
    def fills(self, since: str | None = None) -> list[Fill]:
        if since is None:
            return list(self._fills)
        return [f for f in self._fills if f.timestamp.isoformat() >= since]

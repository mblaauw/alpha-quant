from __future__ import annotations

from typing import override

import duckdb

from alpha_quant.application.store._crud import load_many, load_one, save_row
from alpha_quant.domain.models import Fill, Order
from alpha_quant.ports.store import OrderStore

ORDER_COLS = [
    "order_id",
    "symbol",
    "action",
    "quantity",
    "order_type",
    "limit_price",
    "status",
    "submitted_at",
    "fill_date",
    "filled_quantity",
    "avg_fill_price",
]
FILL_COLS = ["fill_id", "order_id", "symbol", "quantity", "price", "filled_at", "fee"]


class OrderStoreMixin(OrderStore):
    _state_conn: duckdb.DuckDBPyConnection

    @override
    def save_order(self, order: Order) -> None:
        save_row(
            self._state_conn,
            "orders",
            ORDER_COLS,
            [
                order.order_id,
                order.symbol,
                order.action,
                order.quantity,
                order.order_type,
                order.limit_price,
                order.status,
                order.submitted_at,
                order.fill_date,
                order.filled_quantity,
                order.avg_fill_price,
            ],
        )

    @override
    def load_order(self, order_id: str) -> Order | None:
        return load_one(self._state_conn, "orders", ORDER_COLS, Order, "order_id = ?", [order_id])

    @override
    def save_fill(self, fill: Fill) -> None:
        save_row(
            self._state_conn,
            "fills",
            FILL_COLS,
            [
                fill.fill_id,
                fill.order_id,
                fill.symbol,
                fill.quantity,
                fill.price,
                fill.timestamp,
                fill.fee,
            ],
        )

    @override
    def load_fills(self, order_id: str) -> list[Fill]:
        return load_many(
            self._state_conn,
            "fills",
            FILL_COLS,
            Fill,
            "order_id = ?",
            [order_id],
            "filled_at",
        )

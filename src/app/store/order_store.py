from __future__ import annotations

from typing import override

import duckdb

from domain.models import Fill, Order
from ports.store import OrderStore


class OrderStoreMixin(OrderStore):
    _state_conn: duckdb.DuckDBPyConnection

    @override
    def save_order(self, order: Order) -> None:
        self._state_conn.execute(
            "INSERT OR REPLACE INTO orders"
            " (order_id, symbol, action, quantity, order_type, limit_price, status,"
            "  submitted_at, fill_date, filled_quantity, avg_fill_price)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
        row = self._state_conn.execute(
            "SELECT order_id, symbol, action, quantity, order_type, limit_price, status,"
            " submitted_at, fill_date, filled_quantity, avg_fill_price"
            " FROM orders WHERE order_id = ?",
            [order_id],
        ).fetchone()
        if row is None:
            return None
        return Order(
            order_id=row[0],
            symbol=row[1],
            action=row[2],
            quantity=row[3],
            order_type=row[4],
            limit_price=row[5],
            status=row[6],
            submitted_at=row[7],
            fill_date=row[8],
            filled_quantity=row[9],
            avg_fill_price=row[10],
        )

    @override
    def save_fill(self, fill: Fill) -> None:
        self._state_conn.execute(
            "INSERT OR REPLACE INTO fills"
            " (fill_id, order_id, symbol, quantity, price, filled_at, fee)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
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
        rows = self._state_conn.execute(
            "SELECT fill_id, order_id, symbol, quantity, price, filled_at, fee"
            " FROM fills WHERE order_id = ? ORDER BY filled_at",
            [order_id],
        ).fetchall()
        return [
            Fill(
                fill_id=r[0],
                order_id=r[1],
                symbol=r[2],
                quantity=r[3],
                price=r[4],
                timestamp=r[5],
                fee=r[6],
            )
            for r in rows
        ]

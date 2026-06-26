from __future__ import annotations

from typing import override

import duckdb

from alpha_quant.application.store._crud import load_many, save_row
from alpha_quant.domain.models import PortfolioSnapshot, Position
from alpha_quant.ports.store import PositionStore

POSITION_COLS = [
    "symbol",
    "quantity",
    "entry_price",
    "avg_cost",
    "current_price",
    "stop_price",
    "trail_price",
    "market_value",
    "unrealized_pl",
    "realized_pl",
    "sector",
    "decision_id",
    "entry_date",
    "high_since_entry",
    "partial_taken",
]
SNAPSHOT_COLS = ["equity_date", "equity", "cash", "regime", "book"]


class PositionStoreMixin(PositionStore):
    _state_conn: duckdb.DuckDBPyConnection

    @override
    def save_position(self, position: Position) -> None:
        save_row(
            self._state_conn,
            "positions",
            POSITION_COLS,
            [
                position.symbol,
                position.quantity,
                position.entry_price,
                position.avg_cost,
                position.current_price,
                position.stop_price,
                position.trail_price,
                position.market_value,
                position.unrealized_pl,
                position.realized_pl,
                position.sector,
                position.decision_id,
                position.entry_date,
                position.high_since_entry,
                position.partial_taken,
            ],
        )

    @override
    def load_positions(self) -> list[Position]:
        return load_many(self._state_conn, "positions", POSITION_COLS, Position)

    @override
    def save_portfolio_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        book = snapshot.book or "PAPER"
        reg = snapshot.regime or "CAUTION"
        save_row(
            self._state_conn,
            "equity_curve",
            SNAPSHOT_COLS,
            [
                snapshot.date,
                snapshot.equity,
                snapshot.cash,
                reg,
                book,
            ],
        )

    @override
    def load_latest_portfolio_snapshot(self, book: str = "PAPER") -> PortfolioSnapshot | None:
        row = self._state_conn.execute(
            "SELECT equity_date, cash, equity, regime FROM equity_curve"
            " WHERE book = ? ORDER BY equity_date DESC",
            [book],
        ).fetchone()
        if row is None:
            return None
        return PortfolioSnapshot(date=row[0], cash=row[1], equity=row[2], regime=row[3], book=book)

    @override
    def load_portfolio_snapshots(
        self, book: str = "PAPER", limit: int = 500
    ) -> list[PortfolioSnapshot]:
        cols = ["equity_date", "cash", "equity", "regime"]
        return load_many(
            self._state_conn,
            "equity_curve",
            cols,
            PortfolioSnapshot,
            "book = ?",
            [book],
            "equity_date ASC",
            limit,
        )

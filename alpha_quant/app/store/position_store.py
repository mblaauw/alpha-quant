from __future__ import annotations

from typing import override

import duckdb

from alpha_quant.domain.models import PortfolioSnapshot, Position
from alpha_quant.ports.store import PositionStore


class PositionStoreMixin(PositionStore):
    _state_conn: duckdb.DuckDBPyConnection

    @override
    def save_position(self, position: Position) -> None:
        self._state_conn.execute(
            "INSERT OR REPLACE INTO positions"
            " (symbol, quantity, entry_price, avg_cost, current_price, stop_price, trail_price,"
            "  market_value, unrealized_pl, realized_pl, sector, decision_id,"
            "  entry_date, high_since_entry, partial_taken)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
        cols = (
            "symbol, quantity, entry_price, avg_cost, current_price, stop_price, trail_price,"
            " market_value, unrealized_pl, realized_pl, sector, decision_id,"
            " entry_date, high_since_entry, partial_taken"
        )
        rows = self._state_conn.execute(f"SELECT {cols} FROM positions").fetchall()
        return [
            Position(
                symbol=r[0],
                quantity=r[1],
                entry_price=r[2],
                avg_cost=r[3],
                current_price=r[4],
                stop_price=r[5],
                trail_price=r[6],
                market_value=r[7],
                unrealized_pl=r[8],
                realized_pl=r[9],
                sector=r[10],
                decision_id=r[11],
                entry_date=r[12],
                high_since_entry=r[13],
                partial_taken=r[14],
            )
            for r in rows
        ]

    @override
    def save_portfolio_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        book = snapshot.book or "PAPER"
        reg = snapshot.regime or "CAUTION"
        self._state_conn.execute(
            "INSERT OR REPLACE INTO equity_curve"
            " (equity_date, equity, cash, nav, regime, book)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            [snapshot.date, snapshot.equity, snapshot.cash, snapshot.equity, reg, book],
        )

    @override
    def load_latest_portfolio_snapshot(self, book: str = "PAPER") -> PortfolioSnapshot | None:
        row = self._state_conn.execute(
            "SELECT equity_date, cash, equity, regime FROM equity_curve"
            " WHERE book = ?"
            " ORDER BY equity_date DESC LIMIT 1",
            [book],
        ).fetchone()
        if row is None:
            return None
        return PortfolioSnapshot(date=row[0], cash=row[1], equity=row[2], regime=row[3], book=book)

    @override
    def load_portfolio_snapshots(
        self, book: str = "PAPER", limit: int = 500
    ) -> list[PortfolioSnapshot]:
        rows = self._state_conn.execute(
            "SELECT equity_date, cash, equity, regime FROM equity_curve"
            " WHERE book = ? ORDER BY equity_date ASC LIMIT ?",
            [book, limit],
        ).fetchall()
        return [
            PortfolioSnapshot(date=r[0], cash=r[1], equity=r[2], regime=r[3], book=book)
            for r in rows
        ]

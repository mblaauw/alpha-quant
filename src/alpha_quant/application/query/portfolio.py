from __future__ import annotations

from uuid import UUID

from alpha_quant.application.query.shared import (
    resolve_active_book_id,
    with_uow,
)


class PortfolioService:
    def summary(self, book_id: str | None = None) -> dict[str, object]:
        bid = UUID(book_id) if book_id else resolve_active_book_id()

        def _query(uow):
            positions = uow.store.list_positions(bid)
            portfolio = uow.store.load_portfolio(bid)
            total_market_value = sum(float(p.market_value or 0) for p in positions)
            total_cash = float(portfolio.cash) if portfolio else 0.0
            return {
                "cash": total_cash,
                "market_value": total_market_value,
                "equity": total_cash + total_market_value,
                "positions_count": len(positions),
            }

        return with_uow(_query)

    def list_positions(self, book_id: str | None = None) -> list[dict[str, object]]:
        bid = UUID(book_id) if book_id else resolve_active_book_id()

        def _query(uow):
            positions = uow.store.list_positions(bid)
            return [
                {
                    "symbol": p.symbol,
                    "quantity": float(p.quantity) if p.quantity else 0,
                    "avg_cost": float(p.avg_cost) if p.avg_cost else 0,
                    "current_price": float(p.current_price) if p.current_price else 0,
                    "market_value": float(p.market_value) if p.market_value else 0,
                    "unrealized_pl": float(p.unrealized_pl) if p.unrealized_pl else 0,
                    "stop_price": float(p.stop_price) if p.stop_price else 0,
                }
                for p in positions
            ]

        return with_uow(_query)

    def get_position(self, position_id: str) -> dict[str, object] | None:
        def _query(uow):
            positions = uow.store.list_positions(resolve_active_book_id())
            pos = next((p for p in positions if p.symbol == position_id), None)
            if not pos:
                return None
            return {
                "position": {
                    "symbol": pos.symbol,
                    "quantity": float(pos.quantity) if pos.quantity else 0,
                    "avg_cost": float(pos.avg_cost) if pos.avg_cost else 0,
                    "current_price": float(pos.current_price) if pos.current_price else 0,
                    "market_value": float(pos.market_value) if pos.market_value else 0,
                    "unrealized_pl": float(pos.unrealized_pl) if pos.unrealized_pl else 0,
                    "stop_price": float(pos.stop_price) if pos.stop_price else 0,
                },
                "orders": [],
                "fills": [],
            }

        return with_uow(_query)

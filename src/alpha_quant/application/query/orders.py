from __future__ import annotations

from uuid import UUID

from sqlalchemy import text

from alpha_quant.application.query.shared import (
    resolve_active_book_id,
    with_uow,
)


class OrderService:
    def list_orders(
        self,
        book_id: str | None = None,
        status: str | None = None,
        symbol: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, object]:
        bid = UUID(book_id) if book_id else resolve_active_book_id()

        def _query(uow):
            where = ["po.portfolio_book_id = :bid"]
            params: dict[str, object] = {"bid": str(bid), "lim": limit}
            if status:
                where.append("po.status = :status")
                params["status"] = status
            if symbol:
                where.append("po.symbol = :symbol")
                params["symbol"] = symbol
            rows = uow.store.session.execute(
                text(
                    "SELECT po.order_id, po.symbol, po.side, po.quantity, po.status, "
                    "po.filled_quantity, po.submitted_at, po.decision_run_id, po.idempotency_key "
                    "FROM trade.paper_order po WHERE "
                    + " AND ".join(where)
                    + " ORDER BY po.submitted_at DESC LIMIT :lim"
                ),
                params,
            ).fetchall()
            items = [
                {
                    "order_id": str(r[0]),
                    "symbol": r[1],
                    "side": r[2],
                    "quantity": float(r[3]),
                    "status": r[4],
                    "filled_quantity": float(r[5] or 0),
                    "submitted_at": str(r[6]) if r[6] else None,
                    "decision_run_id": str(r[7]) if r[7] else None,
                    "idempotency_key": r[8],
                }
                for r in rows
            ]
            return {"items": items, "next_cursor": None}

        return with_uow(_query)

    def list_fills(
        self,
        book_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, object]:
        bid = UUID(book_id) if book_id else resolve_active_book_id()

        def _query(uow):
            rows = uow.store.session.execute(
                text(
                    "SELECT pf.fill_id, pf.order_id, pf.symbol, pf.side, pf.quantity, "
                    "pf.price, pf.fill_key, pf.quality, pf.fee, pf.booked_at, po.portfolio_book_id "
                    "FROM trade.paper_fill pf "
                    "JOIN trade.paper_order po ON pf.order_id = po.order_id "
                    "WHERE po.portfolio_book_id = :bid "
                    "ORDER BY pf.booked_at DESC LIMIT :lim"
                ),
                {"bid": str(bid), "lim": limit},
            ).fetchall()
            items = [
                {
                    "fill_id": str(r[0]),
                    "order_id": str(r[1]),
                    "symbol": r[2],
                    "side": r[3],
                    "quantity": float(r[4]),
                    "price": float(r[5]),
                    "fill_key": r[6],
                    "quality": r[7],
                    "fee": float(r[8] or 0),
                    "booked_at": str(r[9]) if r[9] else None,
                }
                for r in rows
            ]
            return {"items": items, "next_cursor": None}

        return with_uow(_query)

"""Scorecard and advice query services for console endpoints."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text

from alpha_quant.application.query.shared import resolve_active_book_id, with_uow
from alpha_quant.domain.scorecard import Scorecard


def list_scorecards(
    run_id: str | None = None,
    limit: int = 50,
) -> list[Scorecard]:
    def _query(uow: Any) -> list[Scorecard]:
        if run_id:
            return uow.store.load_scorecards_for_run(run_id)
        from alpha_quant.contracts.operational import RunStatus

        bid = resolve_active_book_id()
        runs = uow.store.list_decision_runs(bid, limit=100)
        last = next(
            (r for r in runs if r.status == RunStatus.COMPLETED),
            None,
        )
        if last:
            return uow.store.load_scorecards_for_run(str(last.decision_run_id))
        return []

    return with_uow(_query)


def get_scorecard(scorecard_id: str) -> Scorecard | None:
    def _query(uow: Any) -> Scorecard | None:
        return uow.store.load_scorecard(scorecard_id)

    return with_uow(_query)


def _compute_sizing(
    equity: float,
    last_price: float,
    atr_value: float | None,
) -> dict[str, object]:
    """Compute one-row sizing preview (mirrors POST /sizing-preview logic)."""
    atr = atr_value if atr_value else last_price * 0.033
    risk_pct = 0.005
    mult = 2.0
    stop_dist = mult * atr
    stop_price = last_price - stop_dist
    risk_budget = equity * risk_pct
    suggested_qty = max(1, int(risk_budget // stop_dist)) if stop_dist > 0 else 1
    notional = suggested_qty * last_price
    risk_at_stop = suggested_qty * stop_dist
    return {
        "suggested_qty": suggested_qty,
        "notional": round(notional, 2),
        "risk_at_stop": round(risk_at_stop, 2),
        "stop_price": round(stop_price, 2),
        "stop_distance": round(stop_dist, 2),
    }


def get_today_advice(
    book_id: UUID | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    def _query(uow: Any) -> list[dict[str, Any]]:
        from alpha_quant.contracts.operational import RunStatus

        bid_filter = ""
        params: dict[str, object] = {
            "status": RunStatus.COMPLETED.value,
            "lim": limit,
        }
        book_uuid = UUID(str(book_id)) if book_id else None
        if book_id:
            bid_filter = " AND dr.portfolio_book_id = :bid"
            params["bid"] = str(book_id)

        sql = f"""
            SELECT DISTINCT ON (s.symbol)
                   dr.decision_run_id, dr.started_at,
                   s.scorecard_id, s.symbol, s.recommendation,
                   s.confidence, s.total_score, s.data_quality,
                   sr.display_name
            FROM run.decision_run dr
            JOIN run.scorecard s ON dr.decision_run_id = s.decision_run_id
            LEFT JOIN core.security_reference sr ON sr.symbol = s.symbol
            WHERE dr.status = :status{bid_filter}
            ORDER BY s.symbol, dr.started_at DESC
            LIMIT :lim
        """  # noqa: E501
        rows = uow.store.session.execute(text(sql), params).fetchall()

        portfolio = uow.store.load_portfolio(book_uuid) if book_uuid else None
        positions = uow.store.list_positions(book_uuid) if book_uuid else []
        cash = float(portfolio.cash) if portfolio and portfolio.cash else 0.0
        total_mv = sum(float(p.market_value or 0) for p in positions)
        equity = cash + total_mv if (cash + total_mv) > 0 else 350_000.0
        price_map: dict[str, float] = {
            p.symbol: float(p.current_price) for p in positions if p.current_price
        }

        results: list[dict[str, Any]] = []
        for r in rows:
            sym = r._mapping["symbol"]
            last_price = price_map.get(sym, 100.0)
            sizing = _compute_sizing(equity, last_price, None)
            results.append(
                {
                    "decision_run_id": r._mapping["decision_run_id"],
                    "run_date": str(r._mapping["started_at"]),
                    "scorecard_id": r._mapping["scorecard_id"],
                    "symbol": sym,
                    "name": r._mapping["display_name"] or "",
                    "recommendation": r._mapping["recommendation"],
                    "confidence": float(r._mapping["confidence"]),
                    "total_score": float(r._mapping["total_score"]),
                    "data_quality": r._mapping["data_quality"],
                    **sizing,
                }
            )
        return results

    return with_uow(_query)


def get_position_advice(
    symbol: str,
    book_id: UUID | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    def _query(uow: Any) -> list[dict[str, Any]]:
        bid_filter = ""
        params: dict[str, object] = {"sym": symbol, "lim": limit}
        if book_id:
            bid_filter = " AND s.portfolio_book_id = :bid"
            params["bid"] = str(book_id)

        rows = uow.store.session.execute(
            text(f"""
                SELECT s.scorecard_id, s.symbol, s.recommendation,
                       s.confidence, s.total_score, s.data_quality,
                       s.created_at
                FROM run.scorecard s
                WHERE s.symbol = :sym{bid_filter}
                ORDER BY s.created_at DESC
                LIMIT :lim
            """),
            params,
        ).fetchall()

        return [
            {
                "scorecard_id": r._mapping["scorecard_id"],
                "symbol": r._mapping["symbol"],
                "recommendation": r._mapping["recommendation"],
                "confidence": float(r._mapping["confidence"]),
                "total_score": float(r._mapping["total_score"]),
                "data_quality": r._mapping["data_quality"],
                "created_at": str(r._mapping["created_at"]),
            }
            for r in rows
        ]

    return with_uow(_query)

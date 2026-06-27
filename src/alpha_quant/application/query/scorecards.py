"""Scorecard and advice query services for console endpoints."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text

from alpha_quant.application.query.shared import with_uow
from alpha_quant.domain.scorecard import Scorecard


def list_scorecards(
    run_id: str | None = None,
    limit: int = 50,
) -> list[Scorecard]:
    def _query(uow: Any) -> list[Scorecard]:
        if run_id:
            return uow.store.load_scorecards_for_run(run_id)
        return []

    return with_uow(_query)


def get_scorecard(scorecard_id: str) -> Scorecard | None:
    def _query(uow: Any) -> Scorecard | None:
        return uow.store.load_scorecard(scorecard_id)

    return with_uow(_query)


def get_today_advice(
    book_id: UUID | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    def _query(uow: Any) -> list[dict[str, Any]]:
        from alpha_quant.contracts.operational import RunStatus

        rows = uow.store.session.execute(
            text("""
                SELECT dr.decision_run_id, dr.started_at,
                       s.scorecard_id, s.symbol, s.recommendation,
                       s.confidence, s.total_score, s.data_quality
                FROM run.decision_run dr
                JOIN run.scorecard s ON dr.decision_run_id = s.decision_run_id
                WHERE dr.status = :status
                  AND (:bid IS NULL OR dr.portfolio_book_id = :bid)
                ORDER BY dr.started_at DESC, s.total_score DESC
                LIMIT :lim
            """),
            {
                "status": RunStatus.COMPLETED.value,
                "bid": str(book_id) if book_id else None,
                "lim": limit,
            },
        ).fetchall()

        results: list[dict[str, Any]] = []
        for r in rows:
            results.append(
                {
                    "decision_run_id": r._mapping["decision_run_id"],
                    "run_date": str(r._mapping["started_at"]),
                    "scorecard_id": r._mapping["scorecard_id"],
                    "symbol": r._mapping["symbol"],
                    "recommendation": r._mapping["recommendation"],
                    "confidence": float(r._mapping["confidence"]),
                    "total_score": float(r._mapping["total_score"]),
                    "data_quality": r._mapping["data_quality"],
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
        rows = uow.store.session.execute(
            text("""
                SELECT s.scorecard_id, s.symbol, s.recommendation,
                       s.confidence, s.total_score, s.data_quality,
                       s.created_at
                FROM run.scorecard s
                WHERE s.symbol = :sym
                  AND (:bid IS NULL OR s.portfolio_book_id = :bid)
                ORDER BY s.created_at DESC
                LIMIT :lim
            """),
            {
                "sym": symbol,
                "bid": str(book_id) if book_id else None,
                "lim": limit,
            },
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

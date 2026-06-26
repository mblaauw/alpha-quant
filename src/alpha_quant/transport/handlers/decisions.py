from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from alpha_quant.application.query.decisions import DecisionService

router = APIRouter(tags=["decisions"])


def _svc() -> DecisionService:
    return DecisionService()


@router.get("/decisions")
async def list_decisions(
    book_id: str | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(50, le=200),
    sort: str = Query("desc"),
    symbol: str | None = Query(None),
    run_id: str | None = Query(None),
    svc: DecisionService = Depends(_svc),
):
    return svc.list_decisions(
        book_id=book_id,
        cursor=cursor,
        limit=limit,
        sort=sort,
        symbol=symbol,
        run_id=run_id,
    )


@router.get("/decisions/{decision_id}")
async def get_decision(
    decision_id: str,
    svc: DecisionService = Depends(_svc),
):
    return svc.get_decision(decision_id)

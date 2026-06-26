from __future__ import annotations

from fastapi import APIRouter, Query

from alpha_quant.application.query.decisions import DecisionService
from alpha_quant.transport.deps import svc_depends

router = APIRouter(tags=["decisions"])


@router.get("/decisions")
async def list_decisions(
    book_id: str | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(50, le=200),
    sort: str = Query("desc"),
    symbol: str | None = Query(None),
    run_id: str | None = Query(None),
    svc: DecisionService = svc_depends(DecisionService),
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
    svc: DecisionService = svc_depends(DecisionService),
):
    return svc.get_decision(decision_id)

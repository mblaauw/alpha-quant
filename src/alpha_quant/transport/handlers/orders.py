from __future__ import annotations

from fastapi import APIRouter, Query

from alpha_quant.application.query.orders import OrderService
from alpha_quant.transport.deps import svc_depends

router = APIRouter(tags=["orders"])


@router.get("/orders")
async def list_orders(
    book_id: str | None = Query(None),
    status: str | None = Query(None),
    symbol: str | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(50, le=200),
    svc: OrderService = svc_depends(OrderService),
):
    return svc.list_orders(
        book_id=book_id,
        status=status,
        symbol=symbol,
        cursor=cursor,
        limit=limit,
    )


@router.get("/fills")
async def list_fills(
    book_id: str | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(50, le=200),
    svc: OrderService = svc_depends(OrderService),
):
    return svc.list_fills(book_id=book_id, cursor=cursor, limit=limit)

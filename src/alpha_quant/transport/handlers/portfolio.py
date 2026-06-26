from __future__ import annotations

from fastapi import APIRouter, Query

from alpha_quant.application.query.portfolio import PortfolioService
from alpha_quant.transport.deps import svc_depends

router = APIRouter(tags=["portfolio"])


@router.get("/portfolio")
async def get_portfolio(
    book_id: str | None = Query(None),
    svc: PortfolioService = svc_depends(PortfolioService),
):
    return svc.summary(book_id=book_id)


@router.get("/positions")
async def list_positions(
    book_id: str | None = Query(None),
    svc: PortfolioService = svc_depends(PortfolioService),
):
    return svc.list_positions(book_id=book_id)


@router.get("/positions/{position_id}")
async def get_position(
    position_id: str,
    svc: PortfolioService = svc_depends(PortfolioService),
):
    return svc.get_position(position_id)

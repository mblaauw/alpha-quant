from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from alpha_quant.application.query.portfolio import PortfolioService

router = APIRouter(tags=["portfolio"])


def _svc() -> PortfolioService:
    return PortfolioService()


@router.get("/portfolio")
async def get_portfolio(
    book_id: str | None = Query(None),
    svc: PortfolioService = Depends(_svc),
):
    return svc.summary(book_id=book_id)


@router.get("/positions")
async def list_positions(
    book_id: str | None = Query(None),
    svc: PortfolioService = Depends(_svc),
):
    return svc.list_positions(book_id=book_id)


@router.get("/positions/{position_id}")
async def get_position(
    position_id: str,
    svc: PortfolioService = Depends(_svc),
):
    return svc.get_position(position_id)

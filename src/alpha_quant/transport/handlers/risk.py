from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from alpha_quant.application.query.risk import RiskService

router = APIRouter(tags=["risk"])


def _svc() -> RiskService:
    return RiskService()


@router.get("/risk")
async def get_risk(book_id: str | None = Query(None), svc: RiskService = Depends(_svc)):
    return svc.summary(book_id=book_id)

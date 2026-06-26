from __future__ import annotations

from fastapi import APIRouter, Query

from alpha_quant.application.query.risk import RiskService
from alpha_quant.transport.deps import svc_depends

router = APIRouter(tags=["risk"])


@router.get("/risk")
async def get_risk(book_id: str | None = Query(None), svc: RiskService = svc_depends(RiskService)):
    return svc.summary(book_id=book_id)

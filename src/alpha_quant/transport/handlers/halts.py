from __future__ import annotations

from fastapi import APIRouter, Depends

from alpha_quant.application.query.risk import RiskService

router = APIRouter(tags=["halts"])


def _svc() -> RiskService:
    return RiskService()


@router.get("/halts")
async def get_halts(svc: RiskService = Depends(_svc)):
    return svc.halt_state()

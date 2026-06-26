from __future__ import annotations

from fastapi import APIRouter

from alpha_quant.application.query.risk import RiskService
from alpha_quant.transport.deps import svc_depends

router = APIRouter(tags=["halts"])


@router.get("/halts")
async def get_halts(svc: RiskService = svc_depends(RiskService)):
    return svc.halt_state()

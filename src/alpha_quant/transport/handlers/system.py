from __future__ import annotations

from fastapi import APIRouter

from alpha_quant.application.query.system import SystemService
from alpha_quant.transport.deps import svc_depends

router = APIRouter(tags=["system"])


@router.get("/context")
async def get_context(svc: SystemService = svc_depends(SystemService)):
    return svc.context()


@router.get("/system")
async def get_system(svc: SystemService = svc_depends(SystemService)):
    return svc.full_status()

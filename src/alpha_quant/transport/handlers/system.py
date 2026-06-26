from __future__ import annotations

from fastapi import APIRouter, Depends

from alpha_quant.application.query.system import SystemService

router = APIRouter(tags=["system"])


def _svc() -> SystemService:
    return SystemService()


@router.get("/context")
async def get_context(svc: SystemService = Depends(_svc)):
    return svc.context()


@router.get("/system")
async def get_system(svc: SystemService = Depends(_svc)):
    return svc.full_status()

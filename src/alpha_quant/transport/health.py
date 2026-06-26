from __future__ import annotations

from fastapi import APIRouter, Depends

from alpha_quant.application.query.system import SystemService

router = APIRouter(tags=["health"])


def _get_system_service() -> SystemService:
    return SystemService()


@router.get("/livez")
async def livez() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/readyz")
async def readyz(svc: SystemService = Depends(_get_system_service)) -> dict[str, object]:
    result = svc.health()
    all_ok = all(v.get("healthy", False) for v in result.get("components", {}).values())
    return {
        "ready": all_ok,
        "checks": result,
    }

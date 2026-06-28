from __future__ import annotations

from typing import Any, cast

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
    components = cast(dict[str, dict[str, Any]], result.get("components", {}))
    all_ok = all(v.get("healthy", False) for v in components.values())
    return {
        "ready": all_ok,
        "checks": result,
    }

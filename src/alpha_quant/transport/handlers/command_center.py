from __future__ import annotations

from fastapi import APIRouter

from alpha_quant.application.query.command_center import CommandCenterService
from alpha_quant.transport.deps import svc_depends

router = APIRouter(tags=["command-center"])


@router.get("/command-center")
async def get_command_center(svc: CommandCenterService = svc_depends(CommandCenterService)):
    return svc.summary()

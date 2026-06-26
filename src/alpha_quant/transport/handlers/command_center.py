from __future__ import annotations

from fastapi import APIRouter, Depends

from alpha_quant.application.query.command_center import CommandCenterService

router = APIRouter(tags=["command-center"])


def _svc() -> CommandCenterService:
    return CommandCenterService()


@router.get("/command-center")
async def get_command_center(svc: CommandCenterService = Depends(_svc)):
    return svc.summary()

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from alpha_quant.application.commands import submit_command
from alpha_quant.application.factory import create_unit_of_work
from alpha_quant.contracts.operational import CommandEnvelope

router = APIRouter(prefix="/v1/commands", tags=["commands"])


def _unit_of_work() -> Any:
    return create_unit_of_work()


class CommandRequest(BaseModel):
    type: str
    idempotency_key: str
    book_id: str | None = None
    reason: str | None = None
    expected_version: int | None = None
    payload: dict = {}


@router.post("")
async def post_command(
    req: CommandRequest,
    x_actor_id: str = Header("operator"),
    x_actor_name: str = Header("Operator"),
):
    envelope = CommandEnvelope(
        type=req.type,
        idempotency_key=req.idempotency_key,
        actor_id=x_actor_id,
        actor_display_name=x_actor_name,
        book_id=UUID(req.book_id) if req.book_id else None,
        reason=req.reason,
        expected_version=req.expected_version,
        payload_json=json.dumps(req.payload, default=str),
    )
    cmd = submit_command(envelope)
    return {"command_id": str(cmd.command_id), "status": cmd.status.value}


@router.get("/{command_id}")
async def get_command(command_id: str, uow: Any = Depends(_unit_of_work)):
    with uow:
        cmd = uow.store.get_command(UUID(command_id))
        if cmd is None:
            raise HTTPException(404, "Command not found")
        return {
            "command_id": str(cmd.command_id),
            "type": cmd.type,
            "status": cmd.status.value,
            "actor_id": cmd.actor_id,
            "actor_display_name": cmd.actor_display_name,
            "book_id": str(cmd.book_id) if cmd.book_id else None,
            "reason": cmd.reason,
            "failure_code": cmd.failure_code,
            "failure_message": cmd.failure_message,
            "requested_at": str(cmd.requested_at) if cmd.requested_at else None,
            "started_at": str(cmd.started_at) if cmd.started_at else None,
            "finished_at": str(cmd.finished_at) if cmd.finished_at else None,
        }


@router.get("")
async def list_commands(
    limit: int = Query(50, ge=1, le=200),
    book_id: str | None = Query(None, max_length=36),
    uow: Any = Depends(_unit_of_work),
):
    with uow:
        cmds = uow.store.list_commands(book_id=UUID(book_id) if book_id else None, limit=limit)
        return {
            "items": [
                {
                    "command_id": str(c.command_id),
                    "type": c.type,
                    "status": c.status.value,
                    "actor_display_name": c.actor_display_name,
                    "reason": c.reason,
                    "requested_at": str(c.requested_at) if c.requested_at else None,
                    "finished_at": str(c.finished_at) if c.finished_at else None,
                }
                for c in cmds
            ]
        }


@router.post("/{command_id}/cancel")
async def cancel_command(command_id: str, uow: Any = Depends(_unit_of_work)):
    from alpha_quant.contracts.operational import CommandStatus

    with uow:
        cmd = uow.store.get_command(UUID(command_id))
        if cmd is None:
            raise HTTPException(404, "Command not found")
        if cmd.status not in (CommandStatus.QUEUED, CommandStatus.RUNNING):
            raise HTTPException(409, "Command is not cancellable")
        uow.store.complete_command(
            UUID(command_id),
            CommandStatus.CANCELLED,
            failure_message="Cancelled by operator",
        )
        return {"command_id": command_id, "status": "cancelled"}

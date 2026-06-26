from __future__ import annotations

import os
from collections.abc import Callable
from uuid import UUID

from alpha_quant.application.factory import create_unit_of_work
from alpha_quant.contracts.operational import (
    Command,
    CommandEnvelope,
    CommandStatus,
    HaltCommand,
    HaltReason,
    RunKind,
    RunReservation,
)

DEFAULT_DATABASE_URL = (
    os.environ.get("DATABASE_URL")
    or "postgresql+psycopg://alpha_quant:alpha_quant_dev@localhost:5433/alpha_quant"
)

CommandHandler = Callable[[Command], tuple[CommandStatus, str | None, str | None]]


def submit_command(
    envelope: CommandEnvelope,
    database_url: str | None = None,
) -> Command:
    uow = create_unit_of_work(database_url or DEFAULT_DATABASE_URL)
    with uow:
        existing = uow.store.get_command_by_idempotency(
            envelope.actor_id, envelope.type, envelope.idempotency_key
        )
        if existing is not None:
            return existing
        cmd = uow.store.submit_command(envelope)
        uow.store.queue_command(cmd.command_id)
        return cmd


def run_decision_handler(cmd: Command) -> tuple[CommandStatus, str | None, str | None]:
    uow = create_unit_of_work()
    with uow:
        run = uow.store.reserve_run(
            RunReservation(
                run_key=f"manual-{cmd.command_id}",
                run_kind=RunKind.DAILY,
                strategy_version_id=UUID("00000000-0000-0000-0000-000000000001"),
                portfolio_book_id=cmd.book_id or UUID("00000000-0000-0000-0000-000000000001"),
                decision_as_of=__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ),
                resolved_snapshot_id="manual",
                alpha_lake_api_version="1.0",
                alpha_lake_contract_version="1.0",
                config_hash="manual",
                request_hash="manual",
                response_hash="manual",
            )
        )
        return CommandStatus.SUCCEEDED, str(run.decision_run_id), None


def create_halt_handler(cmd: Command) -> tuple[CommandStatus, str | None, str | None]:
    uow = create_unit_of_work()
    with uow:
        uow.store.set_halt(
            HaltCommand(
                portfolio_book_id=cmd.book_id or UUID("00000000-0000-0000-0000-000000000001"),
                reason=HaltReason.MANUAL,
                details=cmd.reason or "Operator halt from dashboard",
            )
        )
        return CommandStatus.SUCCEEDED, None, None


def resume_halt_handler(cmd: Command) -> tuple[CommandStatus, str | None, str | None]:
    uow = create_unit_of_work()
    with uow:
        uow.store.clear_halt(cmd.book_id or UUID("00000000-0000-0000-0000-000000000001"))
        return CommandStatus.SUCCEEDED, None, None


HANDLERS: dict[str, CommandHandler] = {
    "decision_run.create": run_decision_handler,
    "halt.create": create_halt_handler,
    "halt.resume": resume_halt_handler,
}


def dispatch(cmd: Command) -> Command:
    handler = HANDLERS.get(cmd.type)
    if handler is None:
        uow = create_unit_of_work()
        with uow:
            uow.store.complete_command(
                cmd.command_id,
                CommandStatus.FAILED,
                failure_code="UNKNOWN_COMMAND",
                failure_message=f"No handler for command type: {cmd.type}",
            )
        return cmd

    try:
        status, result, failure = handler(cmd)
    except Exception as e:
        uow = create_unit_of_work()
        with uow:
            uow.store.complete_command(
                cmd.command_id,
                CommandStatus.FAILED,
                failure_code="HANDLER_ERROR",
                failure_message=str(e),
            )
        return cmd

    uow = create_unit_of_work()
    with uow:
        uow.store.complete_command(
            cmd.command_id,
            status,
            result=result,
            failure_code=None,
            failure_message=failure,
        )
    return cmd

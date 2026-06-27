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
    from alpha_quant.application.config import load_config
    from alpha_quant.application.daily_cycle import DailyCycleService
    from alpha_quant.application.factory import create_alpha_lake_reader

    uow = create_unit_of_work()
    with uow:
        config = load_config()
        alpha_lake = create_alpha_lake_reader(config)
        svc = DailyCycleService(alpha_lake, uow.store)
        book_id = cmd.book_id or UUID("00000000-0000-0000-0000-000000000001")
        result = svc.run(book_id=book_id, run_key=f"cmd-{cmd.command_id}")
        alpha_lake.close()
        if result.halted:
            return CommandStatus.SUCCEEDED, str(result.decision_run_id), "book_halted"
        return CommandStatus.SUCCEEDED, str(result.decision_run_id), None


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


def cancel_order_handler(cmd: Command) -> tuple[CommandStatus, str | None, str | None]:
    import json
    from uuid import UUID

    uow = create_unit_of_work()
    with uow:
        payload = json.loads(cmd.payload_json) if cmd.payload_json else {}
        order_id_str = payload.get("order_id")
        if not order_id_str:
            return CommandStatus.FAILED, None, "Missing order_id in payload"
        try:
            order_id = UUID(order_id_str)
        except ValueError:
            return CommandStatus.FAILED, None, f"Invalid order_id: {order_id_str}"
        uow.store.cancel_order(order_id, cmd.reason)
        return CommandStatus.SUCCEEDED, str(order_id), None


def submit_order_handler(cmd: Command) -> tuple[CommandStatus, str | None, str | None]:
    import json

    uow = create_unit_of_work()
    with uow:
        payload: dict = json.loads(cmd.payload_json) if cmd.payload_json else {}
        symbol: str | None = payload.get("symbol")
        side: str | None = payload.get("side")
        quantity_raw = payload.get("quantity")
        order_type: str = payload.get("order_type", "market")
        if not symbol or not side or quantity_raw is None:
            return CommandStatus.FAILED, None, "Missing required fields: symbol, side, quantity"
        order_id = uow.store.create_order(
            symbol=symbol,
            side=side,
            quantity=float(quantity_raw),
            order_type=order_type,
            book_id=cmd.book_id or UUID("00000000-0000-0000-0000-000000000001"),
            limit_price=payload.get("limit_price"),
        )
        return CommandStatus.SUCCEEDED, order_id, None


def approve_candidate_handler(cmd: Command) -> tuple[CommandStatus, str | None, str | None]:
    import json

    uow = create_unit_of_work()
    with uow:
        payload: dict = json.loads(cmd.payload_json) if cmd.payload_json else {}
        decision_id: str | None = payload.get("decision_id")
        symbol: str | None = payload.get("symbol")
        quantity_raw = payload.get("quantity")
        if not decision_id or not symbol or quantity_raw is None:
            return CommandStatus.FAILED, None, "Missing required fields"
        order_id = uow.store.create_order(
            symbol=symbol,
            side="buy",
            quantity=float(quantity_raw),
            order_type="market",
            book_id=cmd.book_id or UUID("00000000-0000-0000-0000-000000000001"),
            decision_id=decision_id,
        )
        return CommandStatus.SUCCEEDED, order_id, None


def reject_candidate_handler(cmd: Command) -> tuple[CommandStatus, str | None, str | None]:
    import json

    uow = create_unit_of_work()
    with uow:
        payload: dict = json.loads(cmd.payload_json) if cmd.payload_json else {}
        decision_id: str | None = payload.get("decision_id")
        if not decision_id:
            return CommandStatus.FAILED, None, "Missing decision_id"
        uow.store.mark_operator_excluded(decision_id, cmd.reason)
        return CommandStatus.SUCCEEDED, decision_id, None


def flatten_position_handler(cmd: Command) -> tuple[CommandStatus, str | None, str | None]:
    import json

    uow = create_unit_of_work()
    with uow:
        payload: dict = json.loads(cmd.payload_json) if cmd.payload_json else {}
        position_id: str | None = payload.get("position_id")
        if not position_id:
            return CommandStatus.FAILED, None, "Missing position_id"
        positions = uow.store.list_positions(
            cmd.book_id or UUID("00000000-0000-0000-0000-000000000001")
        )
        target = next((p for p in positions if p.symbol == position_id), None)
        if target is None:
            return CommandStatus.FAILED, None, f"Position not found: {position_id}"
        side = "sell" if target.quantity > 0 else "buy"
        order_id = uow.store.create_order(
            symbol=target.symbol,
            side=side,
            quantity=abs(float(target.quantity)),
            order_type="market",
            book_id=cmd.book_id or UUID("00000000-0000-0000-0000-000000000001"),
        )
        return CommandStatus.SUCCEEDED, order_id, None


def set_stop_handler(cmd: Command) -> tuple[CommandStatus, str | None, str | None]:
    import json

    uow = create_unit_of_work()
    with uow:
        payload: dict = json.loads(cmd.payload_json) if cmd.payload_json else {}
        position_id: str | None = payload.get("position_id")
        stop_price_raw = payload.get("stop_price")
        if not position_id or stop_price_raw is None:
            return CommandStatus.FAILED, None, "Missing position_id or stop_price"
        uow.store.update_position_stop(
            symbol=position_id,
            stop_price=float(stop_price_raw),
            book_id=cmd.book_id or UUID("00000000-0000-0000-0000-000000000001"),
        )
        return CommandStatus.SUCCEEDED, position_id, None


def backtest_handler(cmd: Command) -> tuple[CommandStatus, str | None, str | None]:
    import json
    from datetime import datetime

    uow = create_unit_of_work()
    with uow:
        payload = json.loads(cmd.payload_json) if cmd.payload_json else {}
        run_kind_str = payload.get("run_kind", "backtest")
        try:
            run_kind = RunKind(run_kind_str)
        except ValueError:
            return CommandStatus.FAILED, None, f"Invalid run_kind: {run_kind_str}"
        run = uow.store.reserve_run(
            RunReservation(
                run_key=f"cmd-{cmd.command_id}",
                run_kind=run_kind,
                strategy_version_id=UUID("00000000-0000-0000-0000-000000000001"),
                portfolio_book_id=cmd.book_id or UUID("00000000-0000-0000-0000-000000000001"),
                decision_as_of=datetime.fromisoformat(
                    payload.get("to", datetime.now().__str__()).replace("Z", "+00:00")
                ),
                resolved_snapshot_id=payload.get("snapshot_id", ""),
                alpha_lake_api_version="1.0",
                alpha_lake_contract_version="1.0",
                config_hash="cmd",
                request_hash="cmd",
                response_hash="cmd",
            )
        )
        return CommandStatus.SUCCEEDED, str(run.decision_run_id), None


HANDLERS: dict[str, CommandHandler] = {
    "decision_run.create": run_decision_handler,
    "halt.create": create_halt_handler,
    "halt.resume": resume_halt_handler,
    "order.cancel": cancel_order_handler,
    "order.submit": submit_order_handler,
    "candidate.approve": approve_candidate_handler,
    "candidate.reject": reject_candidate_handler,
    "position.flatten": flatten_position_handler,
    "position.set_stop": set_stop_handler,
    "backtest.create": backtest_handler,
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

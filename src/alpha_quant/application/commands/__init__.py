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
        scorecard_id: str | None = payload.get("scorecard_id")
        symbol: str | None = payload.get("symbol")
        quantity_raw = payload.get("quantity")
        if not symbol or quantity_raw is None:
            return CommandStatus.FAILED, None, "Missing required fields: symbol, quantity"
        provenance_id = decision_id or scorecard_id
        order_id = uow.store.create_order(
            symbol=symbol,
            side="buy",
            quantity=float(quantity_raw),
            order_type="market",
            book_id=cmd.book_id or UUID("00000000-0000-0000-0000-000000000001"),
            decision_id=provenance_id,
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


def lake_symbol_add_handler(cmd: Command) -> tuple[CommandStatus, str | None, str | None]:
    import json

    from alpha_quant.application.config import load_config
    from alpha_quant.application.factory import create_alpha_lake_reader

    payload: dict = json.loads(cmd.payload_json) if cmd.payload_json else {}
    symbol: str | None = payload.get("symbol")
    if not symbol:
        return CommandStatus.FAILED, None, "Missing symbol in payload"

    config = load_config()
    lake = create_alpha_lake_reader(config)
    try:
        result = lake.add_symbol(symbol)
        lake.close()
        return CommandStatus.SUCCEEDED, result.status, None
    except Exception as e:
        lake.close()
        return CommandStatus.FAILED, None, f"Alpha-Lake add failed: {e}"


def lake_symbol_remove_handler(cmd: Command) -> tuple[CommandStatus, str | None, str | None]:
    import json

    from alpha_quant.application.config import load_config
    from alpha_quant.application.factory import create_alpha_lake_reader

    payload: dict = json.loads(cmd.payload_json) if cmd.payload_json else {}
    symbol: str | None = payload.get("symbol")
    if not symbol:
        return CommandStatus.FAILED, None, "Missing symbol in payload"

    config = load_config()
    lake = create_alpha_lake_reader(config)
    try:
        result = lake.remove_symbol(symbol)
        lake.close()
        return CommandStatus.SUCCEEDED, result.status, None
    except Exception as e:
        lake.close()
        return CommandStatus.FAILED, None, f"Alpha-Lake remove failed: {e}"


def lake_symbol_refresh_handler(cmd: Command) -> tuple[CommandStatus, str | None, str | None]:
    import json
    from datetime import datetime

    from alpha_quant.application.config import load_config
    from alpha_quant.application.factory import create_alpha_lake_reader

    payload: dict = json.loads(cmd.payload_json) if cmd.payload_json else {}
    symbol: str | None = payload.get("symbol")
    if not symbol:
        return CommandStatus.FAILED, None, "Missing symbol in payload"

    config = load_config()
    lake = create_alpha_lake_reader(config)
    try:
        lake.read_facts_bundle(symbol, datetime.now())
        lake.close()
        return CommandStatus.SUCCEEDED, symbol, None
    except Exception as e:
        lake.close()
        return CommandStatus.FAILED, None, f"Alpha-Lake refresh failed: {e}"


def candidate_modify_handler(cmd: Command) -> tuple[CommandStatus, str | None, str | None]:
    import json

    payload: dict = json.loads(cmd.payload_json) if cmd.payload_json else {}
    scorecard_id: str | None = payload.get("scorecard_id")
    symbol_input: str | None = payload.get("symbol")
    qty_raw = payload.get("qty")
    stop_price_raw = payload.get("stop_price")
    risk_pct_raw = payload.get("risk_pct")
    method: str | None = payload.get("method")

    if not scorecard_id or qty_raw is None:
        return CommandStatus.FAILED, None, "Missing required fields: scorecard_id, qty"

    book_id = cmd.book_id or UUID("00000000-0000-0000-0000-000000000001")
    qty = int(qty_raw)
    stop_price = float(stop_price_raw) if stop_price_raw else None
    risk_pct = float(risk_pct_raw) if risk_pct_raw else None

    uow = create_unit_of_work()
    with uow:
        # Look up symbol from scorecard if not provided in payload
        symbol = symbol_input
        if not symbol:
            sc = uow.store.load_scorecard(scorecard_id)
            if sc:
                symbol = sc.symbol

        if not symbol:
            return CommandStatus.FAILED, None, "Could not resolve symbol from scorecard"

        portfolio = uow.store.load_portfolio(book_id)
        positions = uow.store.list_positions(book_id)
        cash = float(portfolio.cash) if portfolio and portfolio.cash else 0.0
        total_mv = sum(float(p.market_value or 0) for p in positions)
        equity = cash + total_mv if (cash + total_mv) > 0 else 350_000.0

        risk_pct = risk_pct if risk_pct else 0.005
        last_price = stop_price if stop_price else 100.0
        atr = last_price * 0.033

        if method == "atr_2_5":
            stop_dist = 2.5 * atr
        elif method == "fixed_8":
            stop_dist = last_price * 0.08
        else:
            stop_dist = 2.0 * atr
            method = method or "atr_2_0"

        risk_budget = equity * risk_pct
        max_safe_qty = max(1, int(risk_budget // stop_dist)) if stop_dist > 0 else 1
        final_qty = min(qty, max_safe_qty)

        notional = final_qty * last_price
        risk_at_stop = final_qty * stop_dist
        buying_power = equity * 0.18

        if notional > buying_power:
            return (
                CommandStatus.FAILED,
                None,
                f"buying_power_exceeded: ${notional:,.0f} > ${buying_power:,.0f}",
            )
        if final_qty == 0:
            return CommandStatus.FAILED, None, "zero_qty: quantity would be zero"
        if risk_at_stop > equity * 0.01:
            return (
                CommandStatus.FAILED,
                None,
                f"per_trade_risk_exceeded: ${risk_at_stop:,.0f} > 1% of equity",
            )

        order_id = uow.store.create_order(
            symbol=symbol,
            side="buy",
            quantity=float(final_qty),
            order_type="market",
            book_id=book_id,
        )
        return CommandStatus.SUCCEEDED, order_id, None


def risk_profile_update_handler(cmd: Command) -> tuple[CommandStatus, str | None, str | None]:
    import json

    uow = create_unit_of_work()
    with uow:
        payload: dict = json.loads(cmd.payload_json) if cmd.payload_json else {}
        risk_method_id: str | None = payload.get("risk_method_id")
        params_raw = payload.get("params")
        params_json = json.dumps(params_raw) if params_raw else "{}"
        if not risk_method_id:
            return CommandStatus.FAILED, None, "Missing risk_method_id"
        uow.store.set_book_risk_profile(
            book_id=cmd.book_id or UUID("00000000-0000-0000-0000-000000000001"),
            risk_method_id=risk_method_id,
            params_json=params_json,
        )
        return CommandStatus.SUCCEEDED, risk_method_id, None


def position_set_risk_method_handler(cmd: Command) -> tuple[CommandStatus, str | None, str | None]:
    import json

    uow = create_unit_of_work()
    with uow:
        payload: dict = json.loads(cmd.payload_json) if cmd.payload_json else {}
        symbol: str | None = payload.get("symbol")
        risk_method_id: str | None = payload.get("risk_method_id")
        if not symbol or not risk_method_id:
            return CommandStatus.FAILED, None, "Missing symbol or risk_method_id"
        uow.store.update_position_risk(
            book_id=cmd.book_id or UUID("00000000-0000-0000-0000-000000000001"),
            security_id=symbol,
            risk_method_id=risk_method_id,
        )
        return CommandStatus.SUCCEEDED, symbol, None


HANDLERS: dict[str, CommandHandler] = {
    "decision_run.create": run_decision_handler,
    "halt.create": create_halt_handler,
    "halt.resume": resume_halt_handler,
    "order.cancel": cancel_order_handler,
    "order.submit": submit_order_handler,
    "candidate.approve": approve_candidate_handler,
    "candidate.reject": reject_candidate_handler,
    "candidate.modify": candidate_modify_handler,
    "position.flatten": flatten_position_handler,
    "position.set_stop": set_stop_handler,
    "backtest.create": backtest_handler,
    "risk_profile.update": risk_profile_update_handler,
    "position.set_risk_method": position_set_risk_method_handler,
    "lake_symbol.add": lake_symbol_add_handler,
    "lake_symbol.remove": lake_symbol_remove_handler,
    "lake_symbol.refresh": lake_symbol_refresh_handler,
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

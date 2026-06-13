from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

from alpha_quant.domain.events import DomainEvent, FillBooked, OrderSimulated, PartialTaken
from alpha_quant.domain.fills import FillConfig, fill_entry_order, fill_partial_take, fill_stop_loss
from alpha_quant.domain.invariants import InvariantViolation, check_invariants
from alpha_quant.domain.models import (
    Bar,
    Fill,
    Order,
    PortfolioSnapshot,
    Position,
    Quote,
)
from alpha_quant.domain.risk import RiskAction
from alpha_quant.ports.store import Store


@dataclass
class PortfolioResult:
    fills: list[Fill]
    violations: list[InvariantViolation]
    snapshot: PortfolioSnapshot | None = None


class PaperPortfolio:
    def __init__(self, store: Store, run_id: str | None = None) -> None:
        self._store = store
        self._run_id = run_id or uuid.uuid4().hex[:16]
        self._cash: float = 0.0
        self._recover()

    def _recover(self) -> None:
        snap = self._store.load_latest_portfolio_snapshot()
        if snap is not None:
            self._cash = snap.cash

    @property
    def cash(self) -> float:
        return self._cash

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def _emit(self, event: DomainEvent) -> None:
        self._store.save_event(event)

    def initialize(self, equity: float, start_date: date) -> None:
        self._cash = equity
        snap = PortfolioSnapshot(date=start_date, cash=equity, equity=equity)
        self._store.save_portfolio_snapshot(snap)

    def process_entry_orders(
        self,
        orders: list[Order],
        decision_ids: dict[str, str],
        bar: Bar,
        prev_close: float,
        quote: Quote | None = None,
        fill_config: FillConfig | None = None,
    ) -> PortfolioResult:
        fills: list[Fill] = []
        violations: list[InvariantViolation] = []

        for order in orders:
            fill = fill_entry_order(order, bar, prev_close, quote, fill_config)
            if fill is None:
                cancelled = order.model_copy(update={"status": "cancelled"})
                self._store.save_order(cancelled)
                continue

            cost = round(fill.quantity * fill.price, 2)
            if cost > self._cash:
                violations.append(
                    InvariantViolation(
                        check="I7_insufficient_cash",
                        detail=(f"{order.symbol}: need {cost:.2f}, have {self._cash:.2f}"),
                    )
                )
                cancelled = order.model_copy(update={"status": "cancelled"})
                self._store.save_order(cancelled)
                continue

            self._cash -= cost
            self._store.save_fill(fill)

            filled_order = order.model_copy(
                update={
                    "status": "filled",
                    "fill_date": bar.date,
                    "filled_quantity": fill.quantity,
                    "avg_fill_price": fill.price,
                }
            )
            self._store.save_order(filled_order)

            decision_id = decision_ids.get(order.symbol, "")
            position = Position(
                symbol=order.symbol,
                quantity=fill.quantity,
                entry_price=fill.price,
                avg_cost=fill.price,
                current_price=fill.price,
                market_value=cost,
                stop_price=None,
                decision_id=decision_id,
            )
            self._store.save_position(position)

            self._emit(
                OrderSimulated(
                    timestamp=self._now(),
                    run_id=self._run_id,
                    source="paper",
                    order=order,
                )
            )
            self._emit(
                FillBooked(
                    timestamp=self._now(),
                    run_id=self._run_id,
                    source="paper",
                    fill=fill,
                )
            )
            fills.append(fill)

        return PortfolioResult(fills=fills, violations=violations)

    def process_risk_actions(
        self,
        actions: list[RiskAction],
        bar: Bar,
        quote: Quote | None = None,
    ) -> PortfolioResult:
        fills: list[Fill] = []
        violations: list[InvariantViolation] = []
        positions = {p.symbol: p for p in self._store.load_positions()}

        for action in actions:
            position = positions.get(action.symbol)
            if position is None:
                violations.append(
                    InvariantViolation(
                        check="I8_missing_position",
                        detail=(
                            f"Risk action {action.action_type} for {action.symbol}"
                            " but no position found"
                        ),
                    )
                )
                continue

            is_trail = action.action_type == "trail_stop"
            is_partial = action.action_type == "partial_take"
            is_exit = action.action_type in ("stop", "time_stop")

            if is_trail:
                new_stop = action.price
                if new_stop is not None and new_stop > (position.stop_price or 0):
                    self._store.save_position(
                        position.model_copy(
                            update={
                                "stop_price": new_stop,
                                "trail_price": new_stop,
                            }
                        )
                    )

            elif is_exit:
                fill = fill_stop_loss(position, bar, order_id=f"{action.symbol}_stop", quote=quote)
                if fill is None:
                    violations.append(
                        InvariantViolation(
                            check="I9_stop_not_touched",
                            detail=(
                                f"{action.symbol}: stop {position.stop_price}"
                                f" not touched by bar low {bar.low}"
                            ),
                        )
                    )
                    continue

                proceeds = round(abs(fill.quantity) * fill.price, 2)
                realized_pl = round((fill.price - position.avg_cost) * abs(fill.quantity), 2)
                self._cash += proceeds
                self._store.save_fill(fill)
                self._store.save_position(
                    position.model_copy(
                        update={
                            "quantity": 0,
                            "realized_pl": (position.realized_pl or 0) + realized_pl,
                            "current_price": fill.price,
                            "market_value": 0.0,
                        }
                    )
                )
                fills.append(fill)

            elif is_partial:
                order_id = f"{action.symbol}_partial"
                fill = fill_partial_take(position, bar, order_id, quote=quote)
                if fill is None:
                    continue

                sell_qty = abs(fill.quantity)
                proceeds = round(sell_qty * fill.price, 2)
                realized_pl = round((fill.price - position.avg_cost) * sell_qty, 2)
                self._cash += proceeds
                self._store.save_fill(fill)
                remaining_qty = position.quantity - sell_qty
                remaining_value = round(remaining_qty * fill.price, 2)
                self._store.save_position(
                    position.model_copy(
                        update={
                            "quantity": remaining_qty,
                            "market_value": remaining_value,
                            "realized_pl": (position.realized_pl or 0) + realized_pl,
                            "current_price": fill.price,
                        }
                    )
                )
                fills.append(fill)

                self._emit(
                    PartialTaken(
                        timestamp=self._now(),
                        run_id=self._run_id,
                        source="paper",
                        symbol=action.symbol,
                        quantity=sell_qty,
                        price=fill.price,
                    )
                )

            else:
                violations.append(
                    InvariantViolation(
                        check="I10_unknown_risk_action",
                        detail=f"Unknown risk action type: {action.action_type}",
                    )
                )

        return PortfolioResult(fills=fills, violations=violations)

    def mark_to_market(self, run_date: date, prices: dict[str, float]) -> PortfolioSnapshot:
        positions = self._store.load_positions()
        total_mark = 0.0

        for position in positions:
            price = prices.get(position.symbol)
            if price is None:
                continue
            mark = round(position.quantity * price, 2)
            unrel_pl = round((price - position.avg_cost) * position.quantity, 2)
            total_mark += mark
            self._store.save_position(
                position.model_copy(
                    update={
                        "current_price": price,
                        "market_value": mark,
                        "unrealized_pl": unrel_pl,
                    }
                )
            )

        equity = round(self._cash + total_mark, 2)
        snap = PortfolioSnapshot(date=run_date, cash=self._cash, equity=equity)
        self._store.save_portfolio_snapshot(snap)
        return snap

    def self_consistency_check(self) -> list[InvariantViolation]:
        positions = self._store.load_positions()
        total_mark = sum((p.market_value or 0) for p in positions)
        equity = round(self._cash + total_mark, 2)
        return check_invariants(
            equity=equity,
            cash=self._cash,
            positions=positions,
        )

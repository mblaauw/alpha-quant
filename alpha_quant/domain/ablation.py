"""Ablation study configuration and shadow book simulation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict

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

AblationMechanism = Literal["RULES_ONLY", "NO_INSIDER", "NO_CROWDING_VETO"]
ABLATION_MECHANISMS: list[AblationMechanism] = [
    "RULES_ONLY",
    "NO_INSIDER",
    "NO_CROWDING_VETO",
]


class AblationConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    disable_insider: bool = False
    disable_crowding_veto: bool = False


PAPER_CONFIG = AblationConfig()
RULES_ONLY_CONFIG = AblationConfig(disable_insider=True, disable_crowding_veto=True)
NO_INSIDER_CONFIG = AblationConfig(disable_insider=True)
NO_CROWDING_VETO_CONFIG = AblationConfig(disable_crowding_veto=True)

SHADOW_CONFIGS: dict[str, AblationConfig] = {
    "RULES_ONLY": RULES_ONLY_CONFIG,
    "NO_INSIDER": NO_INSIDER_CONFIG,
    "NO_CROWDING_VETO": NO_CROWDING_VETO_CONFIG,
}


@dataclass
class ShadowFillResult:
    fills: list[Fill]
    violations: list[InvariantViolation]


@dataclass
class AblationComparison:
    mechanism: str
    ablation_sharpe: float
    paper_sharpe: float
    diff: float
    flagged: bool


def compute_ablation_comparison(
    paper_returns: list[float],
    ablation_returns: list[float],
    mechanism: str,
) -> AblationComparison | None:
    if len(paper_returns) < 10 or len(ablation_returns) < 10:
        return None

    paper_sharpe = _annualized_sharpe(paper_returns)
    ablation_sharpe = _annualized_sharpe(ablation_returns)

    flagged = ablation_sharpe > paper_sharpe

    return AblationComparison(
        mechanism=mechanism,
        ablation_sharpe=round(ablation_sharpe, 4),
        paper_sharpe=round(paper_sharpe, 4),
        diff=round(ablation_sharpe - paper_sharpe, 4),
        flagged=flagged,
    )


class ShadowBook:
    """A shadow portfolio that runs alongside PAPER with mechanism toggles.

    Maintains positions in-memory and persists PortfolioSnapshots via the Store.
    Uses the same fill model (I8) as the main PAPER book.
    """

    def __init__(
        self,
        book_name: str,
        config: AblationConfig,
        *,
        initial_cash: float = 0.0,
    ) -> None:
        self._book_name = book_name
        self._config = config
        self._cash: float = initial_cash
        self._positions: dict[str, Position] = {}
        self._daily_returns: list[float] = []

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def positions(self) -> list[Position]:
        return list(self._positions.values())

    @property
    def daily_returns(self) -> list[float]:
        return list(self._daily_returns)

    def initialize(self, equity: float, start_date: date) -> PortfolioSnapshot:
        self._cash = equity
        self._positions.clear()
        self._daily_returns.clear()
        return PortfolioSnapshot(date=start_date, cash=equity, equity=equity, book=self._book_name)

    def process_entry_orders(
        self,
        orders: list[Order],
        bar: Bar,
        prev_close: float,
        quote: Quote | None = None,
        fill_config: FillConfig | None = None,
    ) -> ShadowFillResult:
        fills: list[Fill] = []
        violations: list[InvariantViolation] = []

        for order in orders:
            fill = fill_entry_order(order, bar, prev_close, quote, fill_config)
            if fill is None:
                continue

            cost = round(fill.quantity * fill.price, 2)
            if cost > self._cash:
                violations.append(
                    InvariantViolation(
                        check="I7_insufficient_cash",
                        detail=f"{order.symbol}: need {cost:.2f}, have {self._cash:.2f}",
                    )
                )
                continue

            self._cash -= cost

            existing = self._positions.get(order.symbol)
            if existing is not None and existing.quantity > 0:
                total_qty = existing.quantity + fill.quantity
                new_cost = round(
                    (existing.avg_cost * existing.quantity + fill.price * fill.quantity)
                    / total_qty,
                    6,
                )
                pos = existing.model_copy(
                    update={
                        "quantity": total_qty,
                        "avg_cost": new_cost,
                        "entry_price": min(existing.entry_price or fill.price, fill.price),
                        "current_price": fill.price,
                        "market_value": round(total_qty * fill.price, 2),
                        "unrealized_pl": None,
                    }
                )
            else:
                pos = Position(
                    symbol=order.symbol,
                    quantity=fill.quantity,
                    entry_price=fill.price,
                    avg_cost=fill.price,
                    current_price=fill.price,
                    market_value=cost,
                )

            self._positions[order.symbol] = pos
            fills.append(fill)

        return ShadowFillResult(fills=fills, violations=violations)

    def process_risk_actions(
        self,
        actions: list[RiskAction],
        bar: Bar,
        quote: Quote | None = None,
    ) -> ShadowFillResult:
        fills: list[Fill] = []
        violations: list[InvariantViolation] = []

        for action in actions:
            position = self._positions.get(action.symbol)
            if position is None or position.quantity <= 0:
                continue

            is_exit = action.action_type in ("stop", "trail_stop", "time_stop")
            is_partial = action.action_type == "partial_take"

            if is_exit:
                order_id = f"{self._book_name}_{action.symbol}_stop"
                fill = fill_stop_loss(position, bar, order_id, quote=quote)
                if fill is None:
                    violations.append(
                        InvariantViolation(
                            check="I9_stop_not_touched",
                            detail=(f"{action.symbol}: stop not touched by bar low {bar.low}"),
                        )
                    )
                    continue

                proceeds = round(abs(fill.quantity) * fill.price, 2)
                realized_pl = round((fill.price - position.avg_cost) * abs(fill.quantity), 2)
                self._cash += proceeds
                self._positions[action.symbol] = position.model_copy(
                    update={
                        "quantity": 0,
                        "realized_pl": (position.realized_pl or 0) + realized_pl,
                        "current_price": fill.price,
                        "market_value": 0.0,
                    }
                )
                fills.append(fill)

            elif is_partial:
                order_id = f"{self._book_name}_{action.symbol}_partial"
                fill = fill_partial_take(position, bar, order_id, quote=quote)
                if fill is None:
                    continue

                sell_qty = abs(fill.quantity)
                proceeds = round(sell_qty * fill.price, 2)
                realized_pl = round((fill.price - position.avg_cost) * sell_qty, 2)
                self._cash += proceeds
                remaining_qty = position.quantity - sell_qty
                remaining_value = round(remaining_qty * fill.price, 2)
                self._positions[action.symbol] = position.model_copy(
                    update={
                        "quantity": remaining_qty,
                        "market_value": remaining_value,
                        "realized_pl": (position.realized_pl or 0) + realized_pl,
                        "current_price": fill.price,
                    }
                )
                fills.append(fill)

        return ShadowFillResult(fills=fills, violations=violations)

    def mark_to_market(
        self,
        run_date: date,
        prices: dict[str, float],
        prev_equity: float | None = None,
    ) -> PortfolioSnapshot:
        total_mark = 0.0
        for symbol, pos in list(self._positions.items()):
            if pos.quantity <= 0:
                del self._positions[symbol]
                continue

            price = prices.get(symbol)
            if price is None:
                continue

            mark = round(pos.quantity * price, 2)
            unrel_pl = round((price - pos.avg_cost) * pos.quantity, 2)
            total_mark += mark
            self._positions[symbol] = pos.model_copy(
                update={
                    "current_price": price,
                    "market_value": mark,
                    "unrealized_pl": unrel_pl,
                }
            )

        equity = round(self._cash + total_mark, 2)
        snap = PortfolioSnapshot(
            date=run_date, cash=self._cash, equity=equity, book=self._book_name
        )

        if prev_equity is not None and prev_equity > 0:
            daily_ret = (equity - prev_equity) / prev_equity
            self._daily_returns.append(round(daily_ret, 8))

        return snap

    def self_consistency_check(self) -> list[InvariantViolation]:
        active = [p for p in self._positions.values() if p.quantity > 0]
        total_mark = sum(p.market_value or 0 for p in active)
        equity = round(self._cash + total_mark, 2)
        return check_invariants(equity=equity, cash=self._cash, positions=active)


def compute_spy_buy_and_hold(
    spy_bars: list[Bar],
    start_date: date,
    end_date: date,
    initial_equity: float,
) -> list[float]:
    """Compute SPY buy-and-hold equity curve over a date range."""
    bars_sorted = sorted(
        [b for b in spy_bars if start_date <= b.date <= end_date],
        key=lambda b: b.date,
    )
    if not bars_sorted:
        return [initial_equity]

    equity: float = initial_equity
    curve: list[float] = [equity]
    for prev_bar, bar in zip(bars_sorted, bars_sorted[1:], strict=False):
        if bar.date == start_date:
            continue
        if prev_bar.close > 0:
            ret = (bar.close - prev_bar.close) / prev_bar.close
            equity = round(equity * (1 + ret), 2)
        curve.append(equity)

    return curve


def _annualized_sharpe(returns: list[float]) -> float:
    arr = np.array(returns)
    if np.std(arr) < 1e-10:
        return 0.0
    return float(np.mean(arr) / np.std(arr) * np.sqrt(252.0))

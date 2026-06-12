from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from alpha_quant.domain.models import Bar, Position

ActionType = Literal[
    "stop",
    "trail_stop",
    "partial_take",
    "time_stop",
    "drawdown_cut",
    "daily_halt",
]


@dataclass
class RiskConfig:
    stop_atr_mult: float = 2.0
    trail_after_r: float = 1.0
    partial_take_at_r: float = 2.0
    time_stop_days: int = 30
    dd_ladder: list[list[float]] = field(default_factory=lambda: [[0.10, 0.5], [0.15, 0.0]])
    daily_loss_halt_pct: float = 0.03


@dataclass
class RiskAction:
    action_type: ActionType
    symbol: str
    shares: float  # 0 = full exit, >0 = partial reduce
    reason: str


@dataclass
class DrawdownVerdict:
    multiplier: float
    actions: list[RiskAction] = field(default_factory=list)


def evaluate_stops(
    position: Position,
    bar: Bar,
    atr: float,
    highest_since_entry: float,
    config: RiskConfig | None = None,
) -> list[RiskAction]:
    cfg = config or RiskConfig()
    actions: list[RiskAction] = []

    if position.quantity <= 0 or atr <= 0:
        return actions

    entry = position.avg_cost or position.entry_price or bar.close
    if entry <= 0:
        return actions

    r = cfg.stop_atr_mult * atr
    stop_price = entry - r
    highest = max(highest_since_entry, bar.high)

    if bar.low <= stop_price:
        actions.append(
            RiskAction(
                action_type="stop",
                symbol=position.symbol,
                shares=position.quantity,
                reason=f"stop hit at {stop_price:.2f}",
            )
        )
        return actions

    if highest >= entry + r * cfg.trail_after_r:
        trail_price = max(stop_price, entry)
        if bar.low <= trail_price:
            actions.append(
                RiskAction(
                    action_type="trail_stop",
                    symbol=position.symbol,
                    shares=position.quantity,
                    reason=f"trail stop at {trail_price:.2f}",
                )
            )
            return actions

    if highest >= entry + r * cfg.partial_take_at_r:
        partial_qty = position.quantity * 0.5
        actions.append(
            RiskAction(
                action_type="partial_take",
                symbol=position.symbol,
                shares=partial_qty,
                reason=f"partial take at +{cfg.partial_take_at_r}R",
            )
        )

    return actions


def evaluate_time_stop(
    position: Position,
    entry_date: date,
    current_date: date,
    config: RiskConfig | None = None,
) -> list[RiskAction]:
    cfg = config or RiskConfig()
    if position.quantity <= 0:
        return []

    days_held = (current_date - entry_date).days
    if days_held > cfg.time_stop_days:
        return [
            RiskAction(
                action_type="time_stop",
                symbol=position.symbol,
                shares=position.quantity,
                reason=f"time stop after {days_held}d (>{cfg.time_stop_days}d)",
            )
        ]

    return []


def evaluate_drawdown(
    equity_curve: list[float],
    config: RiskConfig | None = None,
) -> DrawdownVerdict:
    cfg = config or RiskConfig()
    if not equity_curve:
        return DrawdownVerdict(multiplier=1.0)

    peak = max(equity_curve)
    current = equity_curve[-1]
    if peak <= 0:
        return DrawdownVerdict(multiplier=1.0)

    dd_pct = (peak - current) / peak
    multiplier = 1.0
    actions: list[RiskAction] = []

    for level, mult in sorted(cfg.dd_ladder, key=lambda x: x[0]):
        if dd_pct >= level:
            multiplier = mult

    if multiplier < 1.0:
        actions.append(
            RiskAction(
                action_type="drawdown_cut",
                symbol="",
                shares=0.0,
                reason=f"drawdown {dd_pct * 100:.1f}% → multiplier {multiplier}",
            )
        )

    return DrawdownVerdict(multiplier=multiplier, actions=actions)


def evaluate_daily_loss(
    today_pnl: float,
    equity: float,
    config: RiskConfig | None = None,
) -> list[RiskAction]:
    cfg = config or RiskConfig()
    if equity <= 0:
        return []

    loss_pct = abs(today_pnl) / equity if today_pnl < 0 else 0.0
    if loss_pct >= cfg.daily_loss_halt_pct:
        return [
            RiskAction(
                action_type="daily_halt",
                symbol="",
                shares=0.0,
                reason=(
                    f"daily loss {loss_pct * 100:.1f}% >= {cfg.daily_loss_halt_pct * 100:.0f}% halt"
                ),
            )
        ]

    return []

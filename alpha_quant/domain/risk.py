from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from alpha_quant.domain.models import Bar, Position

ActionType = Literal[
    "stop",
    "trail_stop",
    "partial_take",
    "time_stop",
    "drawdown_cut",
    "daily_halt",
]


class RiskConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    stop_atr_mult: float = 2.0
    trail_after_r: float = 1.0
    partial_take_at_r: float = 2.0
    time_stop_days: int = 30
    dd_ladder: list[list[float]] = Field(default_factory=lambda: [[0.10, 0.5], [0.15, 0.0]])
    dd_window_days: int = 0
    daily_loss_halt_pct: float = 0.03

    @field_validator("stop_atr_mult", "trail_after_r", "partial_take_at_r")
    @classmethod
    def _r_multiple_bounds(cls, v: float) -> float:
        if not 0.1 <= v <= 10:
            raise ValueError("R-multiple must be between 0.1 and 10")
        return v

    @field_validator("time_stop_days")
    @classmethod
    def _time_stop_days_bounds(cls, v: int) -> int:
        if not 1 <= v <= 365:
            raise ValueError("time_stop_days must be between 1 and 365")
        return v

    @field_validator("daily_loss_halt_pct")
    @classmethod
    def _daily_loss_halt_pct_bounds(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("daily_loss_halt_pct must be between 0.0 and 1.0")
        return v


class RiskAction(BaseModel):
    model_config = ConfigDict(frozen=True)
    action_type: ActionType
    symbol: str
    shares: float  # 0 = full exit, >0 = partial reduce
    reason: str
    price: float | None = None  # new stop price for trail_stop


class DrawdownVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)
    multiplier: float
    actions: list[RiskAction] = Field(default_factory=list)


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
        trail_price = max(highest - r, entry)
        if trail_price > (position.stop_price or 0):
            actions.append(
                RiskAction(
                    action_type="trail_stop",
                    symbol=position.symbol,
                    shares=0.0,
                    reason=f"trail stop adjusted to {trail_price:.2f}",
                    price=trail_price,
                )
            )

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

    if cfg.dd_window_days > 0:
        window = equity_curve[-cfg.dd_window_days :]
        peak = max(window)
    else:
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
                price=multiplier,
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

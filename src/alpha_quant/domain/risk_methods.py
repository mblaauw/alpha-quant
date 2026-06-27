"""Risk method models and deterministic computations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum


class RiskMethodType(StrEnum):
    fixed_percent = "fixed_percent"
    atr_initial = "atr_initial"
    atr_trailing = "atr_trailing"
    time_stop = "time_stop"
    profit_protection = "profit_protection"
    drawdown_ladder = "drawdown_ladder"
    conservative_blended = "conservative_blended"


@dataclass(frozen=True)
class RiskMethodDef:
    risk_method_id: str
    name: str
    description: str
    method_type: RiskMethodType
    default_params_json: str = "{}"
    is_active: bool = True


@dataclass(frozen=True)
class RiskCalculation:
    stop_price: float | None = None
    trail_price: float | None = None
    trail_activation_pct: float | None = None
    time_stop_date: date | None = None
    reason: str = ""


# -- Computation functions --


def compute_fixed_percent_stop(
    entry_price: float,
    *,
    pct: float = 0.10,
    **kwargs: object,
) -> RiskCalculation:
    """Fixed percentage stop below entry price."""
    if entry_price <= 0 or pct <= 0:
        return RiskCalculation(reason="Invalid parameters for fixed percent stop")
    return RiskCalculation(
        stop_price=round(entry_price * (1.0 - pct), 2),
        reason=f"Fixed {pct * 100:.0f}% stop from entry {entry_price:.2f}",
    )


def compute_atr_initial_stop(
    entry_price: float,
    atr: float,
    *,
    multiplier: float = 2.0,
    **kwargs: object,
) -> RiskCalculation:
    """ATR-based initial stop below entry price."""
    if entry_price <= 0 or atr <= 0:
        return RiskCalculation(reason="Invalid parameters for ATR initial stop")
    stop_price = round(entry_price - multiplier * atr, 2)
    if stop_price >= entry_price:
        return RiskCalculation(reason="ATR stop would be above entry price")
    return RiskCalculation(
        stop_price=stop_price,
        reason=f"ATR({multiplier:.0f}x) stop from entry {entry_price:.2f}",
    )


def compute_atr_trailing_stop(
    current_price: float,
    highest_since_entry: float,
    atr: float,
    *,
    multiplier: float = 3.0,
    activation_pct: float = 0.0,
    **kwargs: object,
) -> RiskCalculation:
    """ATR trailing stop that moves up as price increases."""
    if current_price <= 0 or atr <= 0:
        return RiskCalculation(reason="Invalid parameters for ATR trailing stop")
    trail_distance = multiplier * atr
    raw_stop = current_price - trail_distance

    if highest_since_entry > current_price:
        raw_stop = max(raw_stop, highest_since_entry - trail_distance)

    reason = f"ATR trailing ({multiplier:.0f}x) stop at {raw_stop:.2f}"
    return RiskCalculation(
        stop_price=raw_stop,
        trail_price=raw_stop,
        reason=reason,
    )


def compute_time_stop(
    entry_date: date,
    *,
    max_holding_days: int = 60,
    **kwargs: object,
) -> RiskCalculation:
    """Fixed time-based exit."""
    if max_holding_days <= 0:
        return RiskCalculation(reason="Invalid max_holding_days")
    exit_date = entry_date + timedelta(days=max_holding_days)
    return RiskCalculation(
        time_stop_date=exit_date,
        reason=f"Time stop in {max_holding_days}d (exit by {exit_date.isoformat()})",
    )


def compute_profit_protection_trail(
    current_price: float,
    highest_since_entry: float,
    entry_price: float,
    *,
    trail_pct: float = 0.15,
    lock_pct: float = 0.05,
    **kwargs: object,
) -> RiskCalculation:
    """Trailing stop that locks in profits as price rises."""
    if current_price <= 0 or entry_price <= 0:
        return RiskCalculation(reason="Invalid parameters for profit protection")
    profit_pct = (highest_since_entry - entry_price) / entry_price
    if profit_pct <= 0:
        return RiskCalculation(reason="No profit to protect yet")
    trail_price = round(highest_since_entry * (1.0 - trail_pct), 2)
    locked_stop = round(entry_price * (1.0 + lock_pct), 2)
    stop_price = max(trail_price, locked_stop)
    return RiskCalculation(
        stop_price=stop_price,
        trail_price=trail_price,
        reason=(
            f"Profit protection: -{trail_pct * 100:.0f}% from high, min +{lock_pct * 100:.0f}%"
        ),
    )


@dataclass(frozen=True)
class LadderStep:
    drawdown_pct: float
    reduction_pct: float


def compute_drawdown_ladder(
    current_equity: float,
    peak_equity: float,
    *,
    ladder_steps: tuple[LadderStep, ...] = (
        LadderStep(drawdown_pct=0.05, reduction_pct=0.25),
        LadderStep(drawdown_pct=0.10, reduction_pct=0.50),
        LadderStep(drawdown_pct=0.15, reduction_pct=0.75),
        LadderStep(drawdown_pct=0.20, reduction_pct=1.00),
    ),
    **kwargs: object,
) -> RiskCalculation:
    """Drawdown ladder — progressive exposure reduction as losses mount."""
    if current_equity <= 0 or peak_equity <= 0:
        return RiskCalculation(reason="Invalid equity values")
    dd_pct = (peak_equity - current_equity) / peak_equity
    if dd_pct <= 0:
        return RiskCalculation(reason="No drawdown detected")
    active_step: LadderStep | None = None
    for step in sorted(ladder_steps, key=lambda s: s.drawdown_pct, reverse=True):
        if dd_pct >= step.drawdown_pct:
            active_step = step
            break
    if active_step is None:
        return RiskCalculation(reason=f"Drawdown {dd_pct * 100:.1f}% below first threshold")
    return RiskCalculation(
        stop_price=0,
        reason=(
            f"Drawdown {dd_pct * 100:.1f}%:"
            f" reduce exposure by {active_step.reduction_pct * 100:.0f}%"
        ),
    )


def compute_conservative_blended(
    entry_price: float,
    atr: float | None = None,
    current_price: float | None = None,
    highest_since_entry: float | None = None,
    **kwargs: object,
) -> RiskCalculation:
    """Conservative blended — uses the tightest of available methods."""
    candidates: list[RiskCalculation] = []
    candidates.append(compute_fixed_percent_stop(entry_price, pct=0.08, **kwargs))

    if atr and atr > 0:
        candidates.append(compute_atr_initial_stop(entry_price, atr, multiplier=2.0, **kwargs))

    valid_stops = [c for c in candidates if c.stop_price is not None and c.stop_price < entry_price]
    if not valid_stops:
        return RiskCalculation(reason="Conservative blended: no valid stop computed")
    tightest = min(valid_stops, key=lambda c: float(c.stop_price or 0))
    return RiskCalculation(
        stop_price=tightest.stop_price,
        reason=f"Conservative blended stop at {tightest.stop_price:.2f}",
    )


# Method registry

METHOD_REGISTRY: dict[str, dict[str, object]] = {
    RiskMethodType.fixed_percent.value: {
        "fn": compute_fixed_percent_stop,
        "default_params": {"pct": 0.10},
        "label": "Fixed Percent Stop",
        "description": "Stop at a fixed percentage below entry price",
    },
    RiskMethodType.atr_initial.value: {
        "fn": compute_atr_initial_stop,
        "default_params": {"multiplier": 2.0},
        "label": "ATR Initial Stop",
        "description": "Initial stop based on ATR multiplier from entry",
    },
    RiskMethodType.atr_trailing.value: {
        "fn": compute_atr_trailing_stop,
        "default_params": {"multiplier": 3.0, "activation_pct": 0.0},
        "label": "ATR Trailing Stop",
        "description": "Trailing stop that follows price upward using ATR",
    },
    RiskMethodType.time_stop.value: {
        "fn": compute_time_stop,
        "default_params": {"max_holding_days": 60},
        "label": "Time Stop",
        "description": "Exit after a fixed number of holding days",
    },
    RiskMethodType.profit_protection.value: {
        "fn": compute_profit_protection_trail,
        "default_params": {"trail_pct": 0.15, "lock_pct": 0.05},
        "label": "Profit Protection Trail",
        "description": "Trailing stop that locks in profits above breakeven",
    },
    RiskMethodType.drawdown_ladder.value: {
        "fn": compute_drawdown_ladder,
        "default_params": {},
        "label": "Drawdown Ladder",
        "description": "Progressive exposure reduction as drawdown increases",
    },
    RiskMethodType.conservative_blended.value: {
        "fn": compute_conservative_blended,
        "default_params": {},
        "label": "Conservative Blended",
        "description": "Uses the tightest stop from all applicable methods",
    },
}

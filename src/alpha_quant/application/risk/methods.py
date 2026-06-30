"""METHOD_REGISTRY — 7 risk method computation functions per ADR-0053.

Each function takes position context and returns a RiskCalculation.
Registered in METHOD_REGISTRY for runtime lookup by method_type.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from alpha_quant.domain.risk import MethodFn, RiskCalculation

# ── Method context ────────────────────────────────────────────────────────


class MethodContext:
    """Input data for a risk method computation."""

    def __init__(
        self,
        entry_price: float,
        current_price: float,
        atr: float,
        high_since_entry: float | None = None,
        days_held: int = 0,
        current_drawdown: float = 0.0,
        max_drawdown: float = 0.0,
        **kwargs: Any,
    ) -> None:
        self.entry_price = entry_price
        self.current_price = current_price
        self.atr = atr
        self.high_since_entry = high_since_entry or current_price
        self.days_held = days_held
        self.current_drawdown = current_drawdown
        self.max_drawdown = max_drawdown
        self.extra = kwargs


# ── Method computation functions ──────────────────────────────────────────


def fixed_percent(ctx: MethodContext, pct: float = 0.08) -> RiskCalculation:
    """Fixed percentage stop below entry price."""
    stop = ctx.entry_price * (1.0 - pct)
    return RiskCalculation(
        stop_price=round(stop, 2),
        reason=f"Fixed {pct * 100:.0f}% stop from entry ${ctx.entry_price:.2f}",
        method_type="fixed_percent",
        params_snapshot={"pct": pct},
    )


def atr_initial(ctx: MethodContext, multiplier: float = 2.0) -> RiskCalculation:
    """Initial stop at ATR multiple below entry."""
    stop = ctx.entry_price - multiplier * ctx.atr
    return RiskCalculation(
        stop_price=round(max(stop, 0.01), 2),
        reason=(
            f"ATR initial {multiplier}× stop from entry ${ctx.entry_price:.2f} (ATR ${ctx.atr:.2f})"
        ),
        method_type="atr_initial",
        params_snapshot={"multiplier": multiplier},
    )


def atr_trailing(ctx: MethodContext, multiplier: float = 2.0) -> RiskCalculation:
    """Trailing stop at ATR multiple below highest since entry."""
    highest = max(ctx.high_since_entry, ctx.current_price)
    stop = highest - multiplier * ctx.atr
    trail_act = 0.0
    return RiskCalculation(
        stop_price=round(max(stop, 0.01), 2),
        trail_price=round(max(stop, 0.01), 2),
        trail_activation_pct=trail_act,
        reason=(
            f"ATR trailing {multiplier}× from high ${highest:.2f}"
            f" (ATR ${ctx.atr:.2f}, stop ${stop:.2f})"
        ),
        method_type="atr_trailing",
        params_snapshot={"multiplier": multiplier},
    )


def time_stop(ctx: MethodContext, max_holding_days: int = 30) -> RiskCalculation:
    """Time-based stop after max holding days."""
    expiry = date.today() + timedelta(days=1)
    reason_parts: list[str] = []
    if ctx.days_held >= max_holding_days:
        stop = ctx.current_price * 0.97
        reason_parts.append(f"Holding period exceeded ({ctx.days_held} ≥ {max_holding_days}d)")
    else:
        stop = None
        remaining = max_holding_days - ctx.days_held
        reason_parts.append(f"{remaining}d remaining of {max_holding_days}d holding period")

    return RiskCalculation(
        stop_price=round(stop, 2) if stop else None,
        time_stop_date=expiry,
        reason="; ".join(reason_parts),
        method_type="time_stop",
        params_snapshot={"max_holding_days": max_holding_days},
    )


def profit_protection(
    ctx: MethodContext,
    trail_after_r: float = 1.0,
    trail_atr_mult: float = 1.5,
) -> RiskCalculation:
    """Trailing stop activated after profit target reached."""
    entry = ctx.entry_price
    current = ctx.current_price
    atr_val = ctx.atr
    r_return = (current - entry) / atr_val if atr_val > 0 else 0.0

    if r_return >= trail_after_r:
        highest = max(ctx.high_since_entry, current)
        stop = highest - trail_atr_mult * atr_val
        trail_act = trail_after_r
        reason = (
            f"Profit target {trail_after_r}R reached ({r_return:.1f}R);"
            f" trailing {trail_atr_mult}× ATR from ${highest:.2f}"
        )
    else:
        stop = entry - 2.0 * atr_val
        trail_act = None
        reason = f"Pre-target ({r_return:.1f}R < {trail_after_r}R); initial stop {2.0}× ATR"

    return RiskCalculation(
        stop_price=round(max(stop, 0.01), 2),
        trail_price=round(max(stop, 0.01), 2) if r_return >= trail_after_r else None,
        trail_activation_pct=trail_act,
        reason=reason,
        method_type="profit_protection",
        params_snapshot={"trail_after_r": trail_after_r, "trail_atr_mult": trail_atr_mult},
    )


def drawdown_ladder(
    ctx: MethodContext,
    dd_levels: list[tuple[float, float]] | None = None,
) -> RiskCalculation:
    """Reduce position size (simulate via tighter stop) at drawdown thresholds."""
    if dd_levels is None:
        dd_levels = [(0.10, 0.5), (0.15, 0.0)]
    dd = abs(ctx.current_drawdown)
    reduction = 1.0
    for threshold, remaining in sorted(dd_levels):
        if dd >= threshold:
            reduction = remaining

    stop = ctx.current_price * (1.0 - 0.02 * reduction)
    return RiskCalculation(
        stop_price=round(max(stop, 0.01), 2),
        reason=(f"Drawdown ladder: {dd * 100:.1f}% DD → {reduction * 100:.0f}% position remaining"),
        method_type="drawdown_ladder",
        params_snapshot={"dd_levels": dd_levels},
    )


def conservative_blended(ctx: MethodContext) -> RiskCalculation:
    """Conservative blended: tightest of ATR trailing and fixed percent."""
    atr_result = atr_trailing(ctx, multiplier=2.0)
    fixed_result = fixed_percent(ctx, pct=0.06)
    atr_stop = atr_result.stop_price or 0.0
    fixed_stop = fixed_result.stop_price or 0.0

    tightest = (
        min(atr_stop, fixed_stop) if atr_stop > 0 and fixed_stop > 0 else (atr_stop or fixed_stop)
    )

    return RiskCalculation(
        stop_price=round(tightest, 2) if tightest > 0 else None,
        reason=(
            f"Conservative blended: ATR ${atr_stop:.2f} vs fixed ${fixed_stop:.2f}"
            f" → using ${tightest:.2f}"
        ),
        method_type="conservative_blended",
        params_snapshot={"atr_multiplier": 2.0, "fixed_pct": 0.06},
    )


# ── Registry ──────────────────────────────────────────────────────────────


METHOD_REGISTRY: dict[str, MethodFn] = {
    "fixed_percent": fixed_percent,
    "atr_initial": atr_initial,
    "atr_trailing": atr_trailing,
    "time_stop": time_stop,
    "profit_protection": profit_protection,
    "drawdown_ladder": drawdown_ladder,
    "conservative_blended": conservative_blended,
}


def list_methods() -> list[dict[str, Any]]:
    """Return metadata for all registered methods."""
    return [
        {
            "method_type": key,
            "name": key.replace("_", " ").title(),
        }
        for key in METHOD_REGISTRY
    ]


def compute(
    method_type: str,
    ctx: MethodContext,
    **params: Any,
) -> RiskCalculation:
    """Look up a method in the registry and compute a RiskCalculation.

    Raises KeyError if method_type is not registered.
    """
    fn = METHOD_REGISTRY[method_type]
    return fn(ctx, **params)

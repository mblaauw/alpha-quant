"""Limits, circuit breakers & risk events — risk policy threshold checking.

WS8 of the real risk engine epic (#612).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from alpha_quant.domain.risk import RiskPolicy


@dataclass(frozen=True)
class PolicyLimits:
    """Deprecated — use RiskPolicy directly instead."""

    gross_exposure_cap: float = 0.90
    var_99_budget: float = 0.04
    drawdown_limit: float = -0.10
    sector_cap: float = 0.70
    single_name_cap: float = 0.25
    daily_loss_limit: float = -0.02


def check_limits(
    gross_exposure: float,
    var_99_pct: float,
    drawdown: float,
    max_drawdown: float,
    sector_weights: list[dict[str, Any]],
    single_name_weights: list[float],
    symbols: list[str],
    limits: RiskPolicy | PolicyLimits | None = None,
) -> list[dict[str, Any]]:
    """Check all risk policy limits and return limit entries.

    Returns [{name, current, limit, utilization, breach}].
    """
    if limits is None:
        p = PolicyLimits()
    elif isinstance(limits, RiskPolicy):
        p = PolicyLimits(
            gross_exposure_cap=limits.gross_exposure_cap,
            var_99_budget=limits.var_99_budget,
            drawdown_limit=limits.drawdown_limit,
            sector_cap=limits.sector_cap,
            single_name_cap=limits.single_name_cap,
            daily_loss_limit=limits.daily_loss_limit,
        )
    else:
        p = limits
    result: list[dict[str, Any]] = []

    result.append(
        {
            "name": "Gross exposure",
            "current": f"{gross_exposure * 100:.1f}%",
            "limit": f"cap {p.gross_exposure_cap * 100:.0f}%",
            "utilization": round(gross_exposure / p.gross_exposure_cap, 4),
            "breach": gross_exposure > p.gross_exposure_cap,
        }
    )

    result.append(
        {
            "name": "1-day 99% VaR",
            "current": f"{var_99_pct * 100:.1f}%",
            "limit": f"budget {p.var_99_budget * 100:.1f}%",
            "utilization": round(var_99_pct / p.var_99_budget, 4),
            "breach": var_99_pct > p.var_99_budget,
        }
    )

    dd_abs = abs(max_drawdown) if max_drawdown < 0 else abs(drawdown)
    dd_limit_abs = abs(p.drawdown_limit)
    result.append(
        {
            "name": "Max drawdown",
            "current": f"{drawdown * 100:.1f}%",
            "limit": f"limit {p.drawdown_limit * 100:.1f}%",
            "utilization": round(dd_abs / dd_limit_abs, 4) if dd_limit_abs > 0 else 0,
            "breach": drawdown < p.drawdown_limit or max_drawdown < p.drawdown_limit,
        }
    )

    if sector_weights:
        top_sector = sector_weights[0]
        result.insert(
            0,
            {
                "name": f"Sector — {top_sector['name']}",
                "current": f"{top_sector['pct'] * 100:.1f}%",
                "limit": f"cap {p.sector_cap * 100:.0f}%",
                "utilization": round(top_sector["pct"] / p.sector_cap, 4),
                "breach": top_sector["breach"],
            },
        )

    top_sn_weight = max(single_name_weights) if single_name_weights else 0.0
    top_sn_symbol = symbols[single_name_weights.index(top_sn_weight)] if single_name_weights else ""
    if top_sn_weight > 0:
        result.append(
            {
                "name": f"Single-name — {top_sn_symbol}",
                "current": f"{top_sn_weight * 100:.1f}%",
                "limit": f"cap {p.single_name_cap * 100:.0f}%",
                "utilization": round(top_sn_weight / p.single_name_cap, 4),
                "breach": top_sn_weight > p.single_name_cap,
            }
        )

    return result


def generate_events(
    limits: list[dict[str, Any]],
    halted: bool = False,
    warn_threshold: float = 0.85,
) -> list[dict[str, Any]]:
    """Generate risk events from limit states.

    breach → crit event, >=warn_threshold utilization → warn event.
    """
    events: list[dict[str, Any]] = []
    now = datetime.now(UTC).strftime("%H:%M")

    for lim in limits:
        util = lim.get("utilization", 0)
        name = lim.get("name", "")
        current = lim.get("current", "")
        limit_str = lim.get("limit", "")
        breach = lim.get("breach", False)

        if breach:
            events.append(
                {
                    "severity": "crit",
                    "title": f"{name} breach",
                    "at": now,
                    "detail": f"{current} exceeds {limit_str}.",
                }
            )
        elif util >= warn_threshold:
            events.append(
                {
                    "severity": "warn",
                    "title": f"{name} near limit",
                    "at": now,
                    "detail": f"{current} uses {util:.0%} of {limit_str}.",
                }
            )

    if not events and not halted:
        events.append(
            {
                "severity": "info",
                "title": "All limits within policy",
                "at": now,
                "detail": "No limit breaches or warnings detected.",
            }
        )

    return events

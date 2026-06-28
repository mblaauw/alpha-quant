"""Stress & scenario analysis — historical replay + hypothetical shocks.

WS4 of the real risk engine epic (#612).
"""

from __future__ import annotations

from typing import Any, cast


def historical_scenarios(
    positions: list[Any],
    equity: float,
    sectors: list[str],
    weights: list[float],
) -> list[dict[str, Any]]:
    """Compute historical scenario P&L.

    Each scenario applies a portfolio-wide shock to current positions.
    """
    if not positions or equity <= 0:
        return []

    gross = sum(w for w in weights if w > 0)
    scenarios = [
        {
            "name": "2008 Global Financial Crisis",
            "kind": "historical",
            "shock_pct": -0.337,
        },
        {
            "name": "COVID-19 crash",
            "kind": "historical",
            "shock_pct": -0.214,
        },
        {
            "name": "2018 Q4 selloff",
            "kind": "historical",
            "shock_pct": -0.166,
        },
    ]

    results: list[dict[str, Any]] = []
    for sc in scenarios:
        shock = cast(float, sc["shock_pct"])
        pnl = shock * gross * equity if gross > 0 else 0.0
        results.append(
            {
                "name": sc["name"],
                "kind": sc["kind"],
                "pnl_usd": round(pnl, 2),
                "pnl_pct": round(shock * gross, 4) if gross > 0 else 0.0,
            }
        )
    return results


def hypothetical_shocks(
    positions: list[Any],
    equity: float,
    sectors: list[str],
    weights: list[float],
) -> list[dict[str, Any]]:
    """Compute hypothetical shock scenarios."""
    results: list[dict[str, Any]] = []

    # Technology −15%
    tech_weight = sum(w for w, s in zip(weights, sectors, strict=False) if s == "Technology")
    tech_pnl = -0.15 * tech_weight * equity
    results.append(
        {
            "name": "Technology −15%",
            "kind": "hypothetical",
            "pnl_usd": round(tech_pnl, 2),
            "pnl_pct": round(-0.15 * tech_weight, 4),
        }
    )

    # Volatility spike +10 VIX (high-beta positions hit harder)
    beta_avg = 1.0
    vix_pnl = -0.10 * beta_avg * sum(w for w in weights if w > 0) * equity
    results.append(
        {
            "name": "Volatility spike +10 VIX",
            "kind": "hypothetical",
            "pnl_usd": round(vix_pnl, 2),
            "pnl_pct": round(-0.10 * beta_avg * sum(w for w in weights if w > 0), 4),
        }
    )

    # Rates +100bp (Financials benefit, others neutral/negative)
    fin_weight = sum(w for w, s in zip(weights, sectors, strict=False) if s in ("Financials",))
    non_fin_weight = sum(w for w in weights if w > 0) - fin_weight
    rates_pnl = 0.02 * fin_weight * equity - 0.01 * non_fin_weight * equity
    results.append(
        {
            "name": "Rates +100bp",
            "kind": "hypothetical",
            "pnl_usd": round(rates_pnl, 2),
            "pnl_pct": round(rates_pnl / equity if equity > 0 else 0.0, 4),
        }
    )

    return results


def compute_all(
    positions: list[Any],
    equity: float,
    sectors: list[str],
    weights: list[float],
) -> list[dict[str, Any]]:
    """Return all scenarios ordered by severity (absolute P&L descending)."""
    scenarios = historical_scenarios(positions, equity, sectors, weights) + hypothetical_shocks(
        positions, equity, sectors, weights
    )
    scenarios.sort(key=lambda s: -abs(s.get("pnl_usd", 0)))
    return scenarios

"""Liquidity horizon — ADV-based days-to-liquidate.

WS7 of the real risk engine epic (#612).
"""

from __future__ import annotations

from typing import Any

DEFAULT_ADV: float = 1_000_000_000.0  # $1B fallback when ADV is missing


def days_to_liquidate(shares: float, price: float, adv_usd: float | None) -> float:
    """Compute sessions needed to exit at 20% of ADV.

    days = (shares × price) / (0.20 × ADV)
    """
    adv = adv_usd if adv_usd and adv_usd > 0 else DEFAULT_ADV
    notional = shares * price
    return notional / (0.20 * adv)


def compute_all(
    symbols: list[str],
    shares_list: list[float],
    prices: list[float],
    adv_map: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Compute liquidity horizon for each position."""
    adv_map = adv_map or {}
    results: list[dict[str, Any]] = []
    for sym, sh, px in zip(symbols, shares_list, prices, strict=False):
        adv = adv_map.get(sym)
        days = days_to_liquidate(sh, px, adv)
        results.append(
            {
                "symbol": sym,
                "adv_usd": adv if adv else DEFAULT_ADV,
                "shares": sh,
                "days_to_liquidate": round(days, 4),
            }
        )
    return results

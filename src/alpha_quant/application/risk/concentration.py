"""Concentration & diversification metrics — HHI, effective N, correlation, sectors.

WS5 of the real risk engine epic (#612).
"""

from __future__ import annotations

import math
from typing import Any


def hhi(weights: list[float]) -> float:
    """Herfindahl-Hirschman Index × 10,000."""
    return sum(w * w for w in weights) * 10000


def effective_n(hhi_fraction: float) -> float:
    """Effective number of bets = 1 / HHI_fraction."""
    return 1 / hhi_fraction if hhi_fraction > 0 else 0.0


def top_n_concentration(weights: list[float], n: int = 3) -> float:
    """Sum of top N weights."""
    return sum(sorted(weights, reverse=True)[:n])


def avg_pairwise_correlation(returns_matrix: list[list[float]]) -> float:
    """Mean of upper-triangular pairwise correlations.

    Each row in returns_matrix is a position's return series.
    """
    n = len(returns_matrix)
    if n < 2:
        return 0.0
    total_corr = 0.0
    count = 0
    for i in range(n):
        for j in range(i + 1, n):
            r = _pearson(returns_matrix[i], returns_matrix[j])
            total_corr += r
            count += 1
    return total_corr / count if count > 0 else 0.0


def diversification_ratio(vols: list[float], portfolio_vol: float) -> float:
    """Diversification ratio = sum(σ_i) / σ_p."""
    if portfolio_vol <= 0:
        return 1.0
    return sum(vols) / portfolio_vol


def sector_weights(weights: list[float], sectors: list[str]) -> list[dict[str, Any]]:
    """Group weights by sector, compare to cap."""
    sector_map: dict[str, float] = {}
    for w, s in zip(weights, sectors, strict=False):
        sector_map[s] = sector_map.get(s, 0.0) + w
    sorted_sectors = sorted(sector_map.items(), key=lambda x: -x[1])
    return [
        {
            "name": name,
            "pct": round(pct, 4),
            "cap": 0.70,
            "breach": pct > 0.70,
        }
        for name, pct in sorted_sectors
    ]


def compute_all(
    weights: list[float],
    sectors: list[str],
    returns_matrix: list[list[float]] | None = None,
    vols: list[float] | None = None,
    portfolio_vol: float | None = None,
) -> dict[str, Any]:
    """Compute all concentration metrics."""
    hhi_val = hhi(weights)
    hhi_frac = hhi_val / 10000
    en = effective_n(hhi_frac)
    top3 = top_n_concentration(weights)
    avg_corr = avg_pairwise_correlation(returns_matrix) if returns_matrix else 0.0
    dr = diversification_ratio(vols, portfolio_vol) if vols and portfolio_vol else 1.0
    secs = sector_weights(weights, sectors)

    return {
        "effective_bets": round(en, 1),
        "hhi": round(hhi_val),
        "avg_correlation": round(avg_corr, 2),
        "diversification_ratio": round(dr, 2),
        "top3_pct": round(top3, 4),
        "sectors": secs,
    }


def _pearson(x: list[float], y: list[float]) -> float:
    """Pearson correlation coefficient."""
    n = min(len(x), len(y))
    if n < 2:
        return 0.0
    mx = sum(x[:n]) / n
    my = sum(y[:n]) / n
    num = sum((x[i] - mx) * (y[i] - my) for i in range(n))
    dx = math.sqrt(sum((x[i] - mx) ** 2 for i in range(n)))
    dy = math.sqrt(sum((y[i] - my) ** 2 for i in range(n)))
    if dx * dy == 0:
        return 0.0
    return num / (dx * dy)

"""Component VaR — Euler allocation, marginal contribution, flagging.

WS3 of the real risk engine epic (#612).
"""

from __future__ import annotations

import math
from typing import Any


def marginal_var(
    weights: list[float],
    cov_matrix: list[list[float]],
    portfolio_vol: float | None = None,
) -> list[float]:
    """Compute marginal VaR for each position: ∂VaR/∂w_i.

    MVar_i = (Σ_j w_j × σ_ij) / σ_p
    """
    n = len(weights)
    if n == 0 or portfolio_vol == 0:
        return [0.0] * n
    if portfolio_vol is None:
        var = 0.0
        for i in range(n):
            for j in range(n):
                var += weights[i] * weights[j] * cov_matrix[i][j]
        portfolio_vol = math.sqrt(max(var, 0.0))
    if portfolio_vol <= 0:
        return [0.0] * n

    result: list[float] = []
    for i in range(n):
        mvar_i = sum(weights[j] * cov_matrix[i][j] for j in range(n)) / portfolio_vol
        result.append(mvar_i)
    return result


def component_var(
    weights: list[float],
    cov_matrix: list[list[float]],
    portfolio_var_pct: float,
    portfolio_vol: float | None = None,
    flag_multiplier: float = 1.5,
) -> list[dict[str, Any]]:
    """Compute component VaR per position via Euler allocation.

    CVaR_i = w_i × MVar_i
    Returns list of {pct_of_var: float, weight: float, vol: float, beta: float, flagged: bool}.
    """
    n = len(weights)
    if n == 0 or portfolio_var_pct <= 0:
        return []

    if portfolio_vol is None:
        var = 0.0
        for i in range(n):
            for j in range(n):
                var += weights[i] * weights[j] * cov_matrix[i][j]
        portfolio_vol = math.sqrt(max(var, 0.0))

    mvar = marginal_var(weights, cov_matrix, portfolio_vol)
    total_cvar = sum(w * m for w, m in zip(weights, mvar, strict=False))

    results: list[dict[str, Any]] = []
    for i in range(n):
        cvar_i = weights[i] * mvar[i]
        pct_of_var = cvar_i / total_cvar if total_cvar > 0 else 0.0
        vol_i = math.sqrt(cov_matrix[i][i]) if cov_matrix[i][i] >= 0 else 0.0
        beta_i = mvar[i] / portfolio_vol if portfolio_vol > 0 else 0.0
        flagged = pct_of_var > weights[i] * flag_multiplier and weights[i] > 0

        results.append(
            {
                "pct_of_var": round(pct_of_var, 4),
                "weight": round(weights[i], 4),
                "vol": round(vol_i, 4),
                "beta": round(beta_i, 4),
                "flagged": flagged,
            }
        )

    return results

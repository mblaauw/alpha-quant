"""VaR and Expected Shortfall engine — parametric, historical, Monte Carlo.

WS2 of the real risk engine epic (#612).
"""

from __future__ import annotations

import math
from typing import Any


def _z_score(confidence: float) -> float:
    """Approximate z-score for a given confidence level (one-tailed)."""
    return {
        0.95: 1.645,
        0.99: 2.326,
        0.975: 1.96,
    }.get(confidence, 1.645)


def parametric_var(
    weights: list[float],
    cov_matrix: list[list[float]],
    confidence: float = 0.99,
) -> float:
    """Compute parametric variance-covariance VaR.

    VaR = z × sqrt(w' Σ w)
    Returns positive value representing loss (e.g., 0.036 = 3.6%).
    """
    n = len(weights)
    if n == 0:
        return 0.0
    portfolio_variance = 0.0
    for i in range(n):
        for j in range(n):
            portfolio_variance += weights[i] * weights[j] * cov_matrix[i][j]
    portfolio_vol = math.sqrt(max(portfolio_variance, 0.0))
    z = _z_score(confidence)
    return z * portfolio_vol


def parametric_var_multi(
    weights: list[float],
    cov_matrix: list[list[float]],
    levels: list[tuple[str, float]] | None = None,
) -> dict[str, dict[str, float]]:
    """Compute parametric VaR at multiple confidence levels.

    Returns {p95: {pct}, p99: {pct}, es975: {pct}}.
    """
    if levels is None:
        levels = [("p95", 0.95), ("p99", 0.99), ("es975", 0.975)]
    result: dict[str, dict[str, float]] = {}
    for key, conf in levels:
        pct = parametric_var(weights, cov_matrix, conf)
        result[key] = {"pct": round(pct, 4), "parametric": round(pct, 4)}
    return result


def historical_var(
    portfolio_returns: list[float],
    confidence: float = 0.99,
) -> float:
    """Compute historical simulation VaR.

    Sorts historical portfolio returns and takes the (1-confidence) percentile.
    Returns positive value (loss magnitude).
    """
    if not portfolio_returns:
        return 0.0
    sorted_rets = sorted(portfolio_returns)
    index = max(0, int((1 - confidence) * len(sorted_rets)) - 1)
    return abs(min(sorted_rets[index], 0.0))


def historical_var_multi(
    portfolio_returns: list[float],
    levels: list[tuple[str, float]] | None = None,
) -> dict[str, dict[str, float]]:
    """Compute historical VaR at multiple levels."""
    if levels is None:
        levels = [("p95", 0.95), ("p99", 0.99), ("es975", 0.975)]
    result: dict[str, dict[str, float]] = {}
    for key, conf in levels:
        pct = historical_var(portfolio_returns, conf)
        result[key] = {"historical": round(pct, 4)}
    return result


def expected_shortfall(
    portfolio_returns: list[float],
    confidence: float = 0.975,
) -> float:
    """Compute Expected Shortfall (CVaR) as the average of tail losses.

    Tail = worst (1-confidence) fraction of returns.
    Returns positive value (average loss beyond VaR).
    """
    if not portfolio_returns:
        return 0.0
    sorted_rets = sorted(portfolio_returns)
    n_tail = max(1, int((1 - confidence) * len(sorted_rets)))
    tail = sorted_rets[:n_tail]
    return abs(sum(tail) / len(tail)) if tail else 0.0


def monte_carlo_var(
    weights: list[float],
    cov_matrix: list[list[float]],
    paths: int = 10000,
    seed: int = 42,
    confidence: float = 0.99,
) -> float:
    """Compute Monte Carlo VaR via Cholesky decomposition.

    Deterministic when seed is fixed.
    Returns positive value (loss magnitude).
    """
    n = len(weights)
    if n == 0:
        return 0.0

    # Cholesky decomposition of covariance
    chol: list[list[float]] = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = sum(chol[i][k] * chol[j][k] for k in range(j))
            if i == j:
                val = cov_matrix[i][i] - s
                chol[i][j] = math.sqrt(max(val, 0.0))
            else:
                chol[i][j] = (cov_matrix[i][j] - s) / chol[j][j] if chol[j][j] > 0 else 0.0

    # Deterministic normal samples (Box-Muller)
    rng_state = seed
    portfolio_losses: list[float] = []
    for _ in range(paths):
        # Generate n independent standard normals
        normals: list[float] = []
        for _ in range((n + 1) // 2 + 1):
            rng_state = (rng_state * 1103515245 + 12345) & 0x7FFFFFFF
            u1 = rng_state / 2147483648.0
            rng_state = (rng_state * 1103515245 + 12345) & 0x7FFFFFFF
            u2 = rng_state / 2147483648.0
            normals.append(
                math.sqrt(-2.0 * math.log(max(u1, 1e-10))) * math.cos(2.0 * math.pi * u2)
            )
            normals.append(
                math.sqrt(-2.0 * math.log(max(u1, 1e-10))) * math.sin(2.0 * math.pi * u2)
            )
        normals = normals[:n]

        # Correlated returns
        correlated = [sum(chol[i][j] * normals[j] for j in range(n)) for i in range(n)]
        portfolio_loss = -sum(weights[i] * correlated[i] for i in range(n))
        portfolio_losses.append(portfolio_loss)

    sorted_losses = sorted(portfolio_losses)
    index = max(0, int(confidence * len(sorted_losses)) - 1)
    return max(sorted_losses[index], 0.0)


def monte_carlo_es(
    weights: list[float],
    cov_matrix: list[list[float]],
    paths: int = 10000,
    seed: int = 42,
    confidence: float = 0.975,
) -> float:
    """Compute Monte Carlo Expected Shortfall (tail average beyond VaR).

    Averages the worst (1-confidence) fraction of simulated portfolio losses.
    Returns positive value (average loss in tail).
    """
    n = len(weights)
    if n == 0:
        return 0.0

    chol: list[list[float]] = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = sum(chol[i][k] * chol[j][k] for k in range(j))
            if i == j:
                val = cov_matrix[i][i] - s
                chol[i][j] = math.sqrt(max(val, 0.0))
            else:
                chol[i][j] = (cov_matrix[i][j] - s) / chol[j][j] if chol[j][j] > 0 else 0.0

    rng_state = seed
    portfolio_losses: list[float] = []
    for _ in range(paths):
        normals: list[float] = []
        for _ in range((n + 1) // 2 + 1):
            rng_state = (rng_state * 1103515245 + 12345) & 0x7FFFFFFF
            u1 = rng_state / 2147483648.0
            rng_state = (rng_state * 1103515245 + 12345) & 0x7FFFFFFF
            u2 = rng_state / 2147483648.0
            normals.append(
                math.sqrt(-2.0 * math.log(max(u1, 1e-10))) * math.cos(2.0 * math.pi * u2)
            )
            normals.append(
                math.sqrt(-2.0 * math.log(max(u1, 1e-10))) * math.sin(2.0 * math.pi * u2)
            )
        normals = normals[:n]

        correlated = [sum(chol[i][j] * normals[j] for j in range(n)) for i in range(n)]
        portfolio_loss = -sum(weights[i] * correlated[i] for i in range(n))
        portfolio_losses.append(portfolio_loss)

    sorted_losses = sorted(portfolio_losses)
    n_tail = max(1, int((1 - confidence) * len(sorted_losses)))
    tail = sorted_losses[:n_tail]
    return abs(sum(tail) / len(tail)) if tail else 0.0


def compute_all(
    weights: list[float],
    cov_matrix: list[list[float]],
    portfolio_returns: list[float],
    equity: float,
) -> dict[str, Any]:
    """Compute all VaR/ES measures and return the response block.

    Returns dict matching the var section of the risk API contract:
    {horizon_days, levels: {p95/p99/es975: {pct, usd, parametric, historical, monte_carlo}},
     method_params: {ewma_lambda, hist_window_days, mc_paths}}
    """
    para = parametric_var_multi(weights, cov_matrix)
    hist = historical_var_multi(portfolio_returns)
    es_pct = expected_shortfall(portfolio_returns, 0.975)

    levels: dict[str, dict[str, float | str]] = {}
    for key in ("p95", "p99"):
        pct_para = para.get(key, {}).get("parametric", 0.0)
        pct_hist = hist.get(key, {}).get("historical", 0.0)
        pct_mc = monte_carlo_var(
            weights, cov_matrix, confidence={"p95": 0.95, "p99": 0.99}.get(key, 0.99)
        )
        levels[key] = {
            "pct": round(pct_para, 4),
            "usd": round(equity * pct_para, 2),
            "parametric": f"{pct_para * 100:.1f}%",
            "historical": f"{pct_hist * 100:.1f}%",
            "monte_carlo": f"{pct_mc * 100:.1f}%",
        }

    es_hist = expected_shortfall(portfolio_returns, 0.975)
    es_mc = monte_carlo_es(weights, cov_matrix, confidence=0.975)
    es_para = para.get("es975", {}).get("parametric", 0.0)
    levels["es975"] = {
        "pct": round(es_pct, 4),
        "usd": round(equity * es_pct, 2),
        "parametric": f"{es_para * 100:.1f}%",
        "historical": f"{es_hist * 100:.1f}%",
        "monte_carlo": f"{es_mc * 100:.1f}%",
    }

    return {
        "horizon_days": 1,
        "levels": levels,
        "method_params": {
            "ewma_lambda": 0.94,
            "hist_window_days": len(portfolio_returns) if portfolio_returns else 500,
            "mc_paths": 10000,
        },
    }

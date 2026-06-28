"""Factor exposures — market beta and Barra-style normalized style tilts.

WS6 of the real risk engine epic (#612).
"""

from __future__ import annotations

import math
from typing import Any


def market_beta(
    returns: list[float],
    benchmark_returns: list[float],
) -> float:
    """Market beta via OLS: β = Cov(rᵢ, rₘ) / Var(rₘ)."""
    n = min(len(returns), len(benchmark_returns))
    if n < 5:
        return 1.0
    mr = sum(returns[:n]) / n
    mb = sum(benchmark_returns[:n]) / n
    cov = sum((returns[i] - mr) * (benchmark_returns[i] - mb) for i in range(n))
    var_b = sum((benchmark_returns[i] - mb) ** 2 for i in range(n))
    if var_b <= 0:
        return 1.0
    return cov / var_b


def _z_score(values: list[float]) -> list[float]:
    """Z-score a list of values, winsorized at ±3."""
    n = len(values)
    if n == 0:
        return []
    mu = sum(values) / n
    var = sum((v - mu) ** 2 for v in values) / n
    std = math.sqrt(var) if var > 0 else 1.0
    return [max(-3.0, min(3.0, (v - mu) / std)) for v in values]


def _scale_to_unit(z_scores: list[float]) -> list[float]:
    """Scale z-scores to [-1, +1]."""
    max_abs = max(abs(z) for z in z_scores) if z_scores else 1.0
    return [z / max_abs for z in z_scores] if max_abs > 0 else z_scores


def style_tilts(
    metrics: dict[str, list[float]],
) -> list[dict[str, Any]]:
    """Compute normalized style tilts from metric arrays.

    metrics keys: momentum (12m-1m return), value (CF/Price),
                  size (log market cap), volatility (60d sigma), quality (ROE-D/E composite)
    Each value is a list of floats, one per position.
    """
    style_names = ["Momentum", "Value↔Growth", "Size", "Volatility", "Quality"]
    style_keys = ["momentum", "value", "size", "volatility", "quality"]
    invert = {"size": True, "value": True}

    raw_tilts: dict[str, list[float]] = {}
    for key in style_keys:
        vals = metrics.get(key, [])
        if len(vals) < 2:
            raw_tilts[key] = [0.0] * max(len(next(iter(metrics.values()), [])), 1)
        else:
            z = _z_score(vals)
            if invert.get(key, False):
                z = [-x for x in z]
            raw_tilts[key] = _scale_to_unit(z)

    n = max((len(v) for v in raw_tilts.values()), default=0)
    results: list[dict[str, Any]] = []
    for i in range(n):
        if i == 0:
            for idx, key in enumerate(style_keys):
                val = raw_tilts[key][i] if i < len(raw_tilts[key]) else 0.0
                results.append(
                    {
                        "name": style_names[idx],
                        "tilt": round(val, 4),
                    }
                )
    return results


def compute_all(
    returns_matrix: list[list[float]],
    benchmark_returns: list[float],
    extra_metrics: dict[str, list[float]] | None = None,
) -> dict[str, Any]:
    """Compute beta and style tilts.

    Returns {beta: float, styles: [{name, tilt}]}.
    """
    if not returns_matrix:
        return {"beta": 0.0, "styles": []}

    n = len(returns_matrix)
    weights = [1.0 / n] * n

    # Portfolio beta: weighted average of individual betas
    betas: list[float] = []
    for r in returns_matrix:
        betas.append(market_beta(r, benchmark_returns))
    portfolio_beta = sum(w * b for w, b in zip(weights, betas, strict=False))

    metrics = extra_metrics or {}
    styles = style_tilts(metrics)

    return {
        "beta": round(portfolio_beta, 4),
        "styles": styles,
    }

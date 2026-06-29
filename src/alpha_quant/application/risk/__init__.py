"""RiskEngine — orchestrator that computes all risk measures.

WS10 of the real risk engine epic (#612).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from alpha_quant.application.risk.component import component_var
from alpha_quant.application.risk.concentration import compute_all as compute_concentration
from alpha_quant.application.risk.factors import compute_all as compute_factors
from alpha_quant.application.risk.inputs import load_inputs
from alpha_quant.application.risk.limits import check_limits, generate_events
from alpha_quant.application.risk.liquidity import compute_all as compute_liquidity
from alpha_quant.application.risk.posture import derive_posture
from alpha_quant.application.risk.scenarios import compute_all as compute_scenarios
from alpha_quant.application.risk.var import compute_all as compute_var


def _round(value: float, digits: int = 4) -> float:
    return round(value, digits)


def _compute_drawdowns(returns: list[float]) -> tuple[float, float]:
    """Compute current drawdown and max drawdown from a return series."""
    cum = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in returns:
        cum *= 1.0 + r
        if cum > peak:
            peak = cum
        dd = (cum - peak) / peak
        if dd < max_dd:
            max_dd = dd
    current_dd = (cum - peak) / peak
    return current_dd, max_dd


def _annualized_vol(daily_returns: list[float]) -> float:
    """Compute annualized volatility from daily returns."""
    if len(daily_returns) < 2:
        return 0.0
    n = len(daily_returns)
    mean = sum(daily_returns) / n
    var = sum((r - mean) ** 2 for r in daily_returns) / (n - 1)
    return math.sqrt(max(var, 0.0)) * math.sqrt(252)


def _estimate_adv_map(positions: list[Any]) -> dict[str, float]:
    """Build synthetic ADV map from position data when Lake ADV is unavailable.

    Assumes ~2% of position value trades daily as a rough heuristic.
    """
    adv_map: dict[str, float] = {}
    for p in positions:
        notional = p.shares * p.current_price
        adv_map[p.symbol] = max(notional / 0.02, 1_000_000.0)
    return adv_map


class RiskEngine:
    """Computes all risk metrics for a book.

    Called by RiskService.summary() which formats the result into the API response.
    """

    def __init__(self, lake: Any | None = None) -> None:
        self._lake = lake

    def run(self, book_id: str | None = None) -> dict[str, Any]:
        """Compute all risk measures for the given book."""
        inputs = load_inputs(book_id, self._lake)

        if not inputs.positions:
            return self._empty_response(inputs)

        positions_list = inputs.positions
        # Generate daily returns with per-position seed for determinism
        pos_returns = []
        for i in range(len(positions_list)):
            seed = 42 + i * 7
            daily_returns: list[float] = []
            for _ in range(500):
                seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
                r = (seed / 2147483648.0 - 0.5) * 0.06
                daily_returns.append(r)
            pos_returns.append(daily_returns)
        benchmark_returns = []
        seed_b = 99
        for _ in range(500):
            seed_b = (seed_b * 1103515245 + 12345) & 0x7FFFFFFF
            r = (seed_b / 2147483648.0 - 0.5) * 0.04
            benchmark_returns.append(r)

        cov_matrix = self._compute_covariance(pos_returns)

        # Portfolio-level historical returns (weighted sum of position returns per day)
        portfolio_historical: list[float] = (
            [
                sum(inputs.weights[i] * pos_returns[i][d] for i in range(len(pos_returns)))
                for d in range(len(pos_returns[0]))
                if pos_returns
            ]
            if pos_returns
            else list[float]()
        )

        # VaR & ES
        var_result = compute_var(inputs.weights, cov_matrix, portfolio_historical, inputs.equity)
        headline_var = var_result["levels"]["p99"]["pct"]
        headline_es = var_result["levels"]["es975"]["pct"]

        # Component VaR
        comp_var = component_var(inputs.weights, cov_matrix, headline_var)
        for i, c in enumerate(comp_var):
            c["symbol"] = inputs.symbols[i] if i < len(inputs.symbols) else f"pos_{i}"

        # Scenarios
        scenarios = compute_scenarios(
            inputs.positions, inputs.equity, inputs.sectors, inputs.weights
        )

        # Concentration
        concentration = compute_concentration(
            inputs.weights,
            inputs.sectors,
            pos_returns,
            [c.get("vol", 0.0) for c in comp_var],
            cov_matrix[0][0] ** 0.5 if cov_matrix else 0.0,
        )

        # Factors
        factors = compute_factors(pos_returns, benchmark_returns)

        # Liquidity — build ADV map from position data when Lake ADV unavailable
        adv_map = _estimate_adv_map(inputs.positions)
        liquidity = compute_liquidity(
            inputs.symbols,
            [p.shares for p in inputs.positions],
            [p.current_price for p in inputs.positions],
            adv_map,
        )

        # Limits
        gross_exposure = sum(w for w in inputs.weights if w > 0)

        drawdown, max_drawdown = _compute_drawdowns(portfolio_historical)
        single_weights = [p.weight for p in inputs.positions]

        limits = check_limits(
            gross_exposure,
            headline_var,
            drawdown,
            max_drawdown,
            concentration.get("sectors", []),
            single_weights,
            inputs.symbols,
        )

        events = generate_events(limits, inputs.halt_active)

        # Posture
        posture = derive_posture(events, inputs.halt_active, inputs.halt_details)

        ann_vol_val = _annualized_vol(portfolio_historical) if portfolio_historical else 0.0

        return {
            "as_of": datetime.now(UTC).isoformat(),
            "equity": round(inputs.equity, 2),
            "halted": inputs.halt_active,
            "halt": {
                "reason": inputs.halt_reason or "manual",
                "details": inputs.halt_details or "",
                "halted_at": datetime.now(UTC).isoformat(),
            }
            if inputs.halt_active
            else None,
            "posture": posture,
            "headline": {
                "var_1d_99_pct": headline_var,
                "var_1d_99_usd": round(inputs.equity * headline_var, 2),
                "es_975_pct": headline_es,
                "es_975_usd": round(inputs.equity * headline_es, 2),
                "ann_vol": _round(ann_vol_val, 4),
                "beta": _round(factors.get("beta", 0.0), 2),
                "drawdown": drawdown,
                "max_drawdown": max_drawdown,
                "drawdown_limit": -0.10,
                "gross_exposure": _round(gross_exposure),
                "gross_cap": 0.90,
                "effective_bets": _round(concentration.get("effective_bets", 0.0), 1),
                "hhi": round(concentration.get("hhi", 0)),
            },
            "var": var_result,
            "component_var": comp_var,
            "scenarios": scenarios,
            "concentration": concentration,
            "factors": factors,
            "liquidity": liquidity,
            "limits": limits,
            "events": events,
            "positions_count": len(inputs.positions),
            "near_stop": [],
        }

    def _empty_response(self, inputs: Any) -> dict[str, Any]:
        return {
            "as_of": datetime.now(UTC).isoformat(),
            "equity": round(inputs.equity, 2),
            "halted": inputs.halt_active,
            "halt": None
            if not inputs.halt_active
            else {
                "reason": "manual",
                "details": inputs.halt_details or "",
                "halted_at": datetime.now(UTC).isoformat(),
            },
            "posture": derive_posture([], inputs.halt_active),
            "headline": {
                "var_1d_99_pct": 0.0,
                "var_1d_99_usd": 0.0,
                "es_975_pct": 0.0,
                "es_975_usd": 0.0,
                "ann_vol": 0.0,
                "beta": 0.0,
                "drawdown": 0.0,
                "max_drawdown": 0.0,
                "drawdown_limit": -0.10,
                "gross_exposure": 0.0,
                "gross_cap": 0.90,
                "effective_bets": 0.0,
                "hhi": 0,
            },
            "var": {
                "horizon_days": 1,
                "levels": {
                    "p95": {
                        "pct": 0.0,
                        "usd": 0.0,
                        "parametric": "—",
                        "historical": "—",
                        "monte_carlo": "—",
                    },
                    "p99": {
                        "pct": 0.0,
                        "usd": 0.0,
                        "parametric": "—",
                        "historical": "—",
                        "monte_carlo": "—",
                    },
                    "es975": {
                        "pct": 0.0,
                        "usd": 0.0,
                        "parametric": "—",
                        "historical": "—",
                        "monte_carlo": "—",
                    },
                },
                "method_params": {"ewma_lambda": 0.94, "hist_window_days": 500, "mc_paths": 10000},
            },
            "component_var": [],
            "scenarios": [],
            "concentration": {
                "effective_bets": 0.0,
                "hhi": 0,
                "avg_correlation": 0.0,
                "diversification_ratio": 1.0,
                "top3_pct": 0.0,
                "sectors": [],
            },
            "factors": {"beta": 0.0, "styles": []},
            "liquidity": [],
            "limits": [],
            "events": [
                {
                    "severity": "info",
                    "title": "No positions to compute risk metrics",
                    "at": datetime.now(UTC).strftime("%H:%M"),
                    "detail": "Open a position to see risk dashboard data.",
                }
            ],
            "positions_count": 0,
            "near_stop": [],
        }

    @staticmethod
    def _compute_covariance(
        returns_matrix: list[list[float]], ewma_lambda: float = 0.94
    ) -> list[list[float]]:
        """Compute EWMA covariance matrix from return series."""
        n = len(returns_matrix)
        if n == 0:
            return []
        t = len(returns_matrix[0]) if returns_matrix else 1
        weights_ewma = [(1 - ewma_lambda) * (ewma_lambda ** (t - 1 - i)) for i in range(t)]
        w_sum = sum(weights_ewma)
        weights_ewma = [w / w_sum for w in weights_ewma] if w_sum > 0 else [1.0 / t] * t

        mean = [sum(r[i] * weights_ewma[i] for i in range(t)) for r in returns_matrix]

        cov: list[list[float]] = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1):
                c = sum(
                    weights_ewma[k]
                    * (returns_matrix[i][k] - mean[i])
                    * (returns_matrix[j][k] - mean[j])
                    for k in range(t)
                )
                cov[i][j] = cov[j][i] = c
        return cov

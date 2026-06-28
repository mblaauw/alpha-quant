"""Tests for WS3-WS10 risk engine modules."""

from __future__ import annotations

import math
from typing import Any

from alpha_quant.application.risk import (
    component,
    concentration,
    factors,
    limits,
    liquidity,
    posture,
    scenarios,
)


# ── WS3: Component VaR ──


def test_marginal_var_basic() -> None:
    w = [0.6, 0.4]
    cov = [[0.04, 0.01], [0.01, 0.09]]
    mv = component.marginal_var(w, cov)
    assert len(mv) == 2
    assert all(isinstance(v, float) for v in mv)


def test_component_var_sum_reconciles() -> None:
    w = [0.6, 0.4]
    cov = [[0.04, 0.01], [0.01, 0.09]]
    var_pct = 0.036
    cv = component.component_var(w, cov, var_pct)
    total = sum(c["pct_of_var"] for c in cv)
    assert abs(total - 1.0) < 0.01, f"Sum CVaR = {total}, expected ≈1.0"


def test_component_var_flags_disproportionate() -> None:
    w = [0.9, 0.1]
    cov = [[0.25, 0.02], [0.02, 0.01]]
    cv = component.component_var(w, cov, 0.05)
    # First position has 90% weight but should carry most risk
    assert cv[0]["flagged"] or not cv[1]["flagged"]


def test_marginal_var_empty() -> None:
    assert component.marginal_var([], []) == []


def test_component_var_no_weights() -> None:
    assert component.component_var([], [], 0.05) == []


# ── WS4: Scenarios ──


def test_historical_scenarios_count() -> None:
    positions = [1, 2]
    s = scenarios.historical_scenarios(positions, 100000, ["Technology", "Financials"], [0.6, 0.4])
    assert len(s) == 3


def test_hypothetical_shocks_tech() -> None:
    positions = [1]
    s = scenarios.hypothetical_shocks(positions, 100000, ["Technology"], [1.0])
    tech = [x for x in s if "Technology" in x["name"]]
    assert len(tech) == 1
    assert tech[0]["pnl_usd"] == -15000.0  # -15% × 100% × $100k


def test_hypothetical_shocks_rates() -> None:
    positions = [1, 2]
    s = scenarios.hypothetical_shocks(positions, 100000, ["Financials", "Technology"], [0.5, 0.5])
    rates = [x for x in s if "Rates" in x["name"]]
    assert len(rates) == 1
    # Financials: +2% × 0.5 × $100k = +$1k; Non-Fin: -1% × 0.5 × $100k = -$500; Net: +$500
    assert rates[0]["pnl_usd"] == 500.0


def test_compute_all_ordered_by_severity() -> None:
    positions = [1, 2]
    s = scenarios.compute_all(positions, 100000, ["Technology", "Financials"], [0.6, 0.4])
    assert len(s) == 6
    # Should be ordered by absolute P&L descending
    abs_pnls = [abs(x["pnl_usd"]) for x in s]
    assert abs_pnls == sorted(abs_pnls, reverse=True)


def test_scenarios_empty_positions() -> None:
    assert scenarios.compute_all([], 0, [], []) == []


# ── WS5: Concentration ──


def test_hhi_equal_weight() -> None:
    h = concentration.hhi([0.5, 0.5])
    assert abs(h - 5000.0) < 0.01  # 0.5² + 0.5² = 0.5 → ×10000 = 5000


def test_hhi_single_name() -> None:
    h = concentration.hhi([1.0])
    assert abs(h - 10000.0) < 0.01


def test_effective_n() -> None:
    en = concentration.effective_n(0.5)
    assert abs(en - 2.0) < 0.01


def test_top_n_concentration() -> None:
    top = concentration.top_n_concentration([0.5, 0.3, 0.2], 2)
    assert abs(top - 0.8) < 0.01


def test_avg_pairwise_correlation_perfect() -> None:
    returns = [[1.0, 2.0, 3.0], [1.1, 2.1, 3.1]]
    r = concentration.avg_pairwise_correlation(returns)
    assert abs(r - 1.0) < 0.1  # near perfect


def test_avg_pairwise_correlation_single() -> None:
    assert concentration.avg_pairwise_correlation([[1.0, 2.0]]) == 0.0


def test_diversification_ratio() -> None:
    dr = concentration.diversification_ratio([0.2, 0.3], 0.4)
    assert abs(dr - 1.25) < 0.01  # (0.2+0.3) / 0.4


def test_sector_weights() -> None:
    secs = concentration.sector_weights([0.6, 0.4], ["Technology", "Financials"])
    assert len(secs) == 2
    assert secs[0]["name"] == "Technology"
    assert secs[0]["pct"] == 0.6


def test_sector_breach() -> None:
    secs = concentration.sector_weights([0.8, 0.2], ["Technology", "Financials"])
    assert secs[0]["breach"] is True


def test_compute_all_concentration() -> None:
    result = concentration.compute_all(
        [0.5, 0.5], ["Tech", "Fin"], [[1, 2], [1, 2]], [0.2, 0.3], 0.4
    )
    assert "effective_bets" in result
    assert "hhi" in result
    assert "sectors" in result


# ── WS6: Factors ──


def test_market_beta_one() -> None:
    # Identical returns → beta = 1
    r = [0.01, 0.02, 0.03, 0.04, 0.05]
    b = factors.market_beta(r, r)
    assert abs(b - 1.0) < 0.1


def test_market_beta_half() -> None:
    # Returns half of benchmark → beta ≈ 0.5
    bench = [0.01, 0.02, 0.03, 0.04, 0.05]
    r = [x * 0.5 for x in bench]
    b = factors.market_beta(r, bench)
    assert abs(b - 0.5) < 0.1


def test_market_beta_short_window() -> None:
    assert factors.market_beta([0.01], [0.02]) == 1.0


def test_style_tilts_single_position() -> None:
    result = factors.style_tilts({"momentum": [0.5], "value": [0.3]})
    assert len(result) == 5


def test_compute_all_factors_empty() -> None:
    result = factors.compute_all([], [])
    assert result["beta"] == 0.0
    assert result["styles"] == []


# ── WS7: Liquidity ──


def test_days_to_liquidate() -> None:
    dtl = liquidity.days_to_liquidate(100, 500.0, 1_000_000_000.0)
    # (100 × 500) / (0.20 × 1e9) = 50000 / 200000000 = 0.00025
    assert abs(dtl - 0.00025) < 0.0001


def test_days_to_liquidate_no_adv() -> None:
    dtl = liquidity.days_to_liquidate(100, 500.0, None)
    assert dtl > 0  # fallback ADV used


def test_compute_all_liquidity() -> None:
    result = liquidity.compute_all(["AAPL", "NVDA"], [100, 50], [200.0, 500.0], {"AAPL": 5e9})
    assert len(result) == 2
    assert result[0]["symbol"] == "AAPL"
    assert result[0]["days_to_liquidate"] < 0.001  # very liquid
    assert result[1]["symbol"] == "NVDA"


# ── WS8: Limits ──


def test_check_limits_gross_exposure() -> None:
    lims = limits.check_limits(0.95, 0.03, -0.01, -0.05, [], [], [])
    gross = [l for l in lims if "Gross" in l["name"]]
    assert gross[0]["breach"] is True  # 95% > 90% cap


def test_check_limits_var_budget() -> None:
    lims = limits.check_limits(0.5, 0.05, -0.01, -0.05, [], [], [])
    var_lim = [l for l in lims if "VaR" in l["name"]]
    assert var_lim[0]["breach"] is True  # 5% > 4% budget


def test_check_limits_sector_breach() -> None:
    secs = [{"name": "Technology", "pct": 0.75, "breach": True}]
    lims = limits.check_limits(0.5, 0.03, -0.01, -0.05, secs, [0.5], ["AAPL"])
    sec_lim = [l for l in lims if "Sector" in l["name"]]
    assert sec_lim[0]["breach"] is True


def test_generate_events_crit() -> None:
    lims = [
        {
            "name": "Gross exposure",
            "current": "95%",
            "limit": "cap 90%",
            "utilization": 1.06,
            "breach": True,
        }
    ]
    evts = limits.generate_events(lims)
    assert any(e["severity"] == "crit" for e in evts)


def test_generate_events_warn() -> None:
    lims = [
        {
            "name": "VaR",
            "current": "3.4%",
            "limit": "budget 4%",
            "utilization": 0.88,
            "breach": False,
        }
    ]
    evts = limits.generate_events(lims)
    assert any(e["severity"] == "warn" for e in evts)


def test_generate_events_info_when_clean() -> None:
    evts = limits.generate_events([])
    assert any(e["severity"] == "info" for e in evts)


# ── WS9: Posture ──


def test_posture_halt() -> None:
    p = posture.derive_posture([], halted=True, halt_details="Manual halt")
    assert p["state"] == "halt"


def test_posture_elevated_from_crit() -> None:
    p = posture.derive_posture([{"severity": "crit", "title": "Limit breach"}])
    assert p["state"] == "elevated"
    assert "Critical" in p["text"]


def test_posture_elevated_from_warn() -> None:
    p = posture.derive_posture([{"severity": "warn", "title": "Near limit"}])
    assert p["state"] == "elevated"
    assert "Caution" in p["text"]


def test_posture_ready() -> None:
    p = posture.derive_posture([{"severity": "info", "title": "All good"}])
    assert p["state"] == "ready"


def test_posture_halt_overrides() -> None:
    # halt should override even with crit events
    p = posture.derive_posture([{"severity": "crit", "title": "X"}], halted=True)
    assert p["state"] == "halt"

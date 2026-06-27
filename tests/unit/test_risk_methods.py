from __future__ import annotations

from datetime import date

from alpha_quant.domain.risk_methods import (
    RiskMethodType,
    compute_atr_initial_stop,
    compute_atr_trailing_stop,
    compute_conservative_blended,
    compute_drawdown_ladder,
    compute_fixed_percent_stop,
    compute_profit_protection_trail,
    compute_time_stop,
)


class TestFixedPercentStop:
    def test_basic(self) -> None:
        r = compute_fixed_percent_stop(100.0, pct=0.10)
        assert r.stop_price is not None
        assert r.stop_price == 90.0
        assert "10%" in r.reason

    def test_invalid_entry(self) -> None:
        r = compute_fixed_percent_stop(0.0)
        assert r.stop_price is None
        assert "Invalid" in r.reason

    def test_zero_pct(self) -> None:
        r = compute_fixed_percent_stop(100.0, pct=0.0)
        assert r.stop_price is None


class TestATRInitialStop:
    def test_basic(self) -> None:
        r = compute_atr_initial_stop(100.0, atr=5.0, multiplier=2.0)
        assert r.stop_price is not None
        assert r.stop_price == 90.0

    def test_zero_atr(self) -> None:
        r = compute_atr_initial_stop(100.0, atr=0.0)
        assert r.stop_price is None


class TestATRTrailing:
    def test_basic_trail(self) -> None:
        r = compute_atr_trailing_stop(110.0, 110.0, 3.0, multiplier=3.0)
        assert r.stop_price is not None
        assert r.stop_price == 101.0

    def test_trail_moves_up(self) -> None:
        r = compute_atr_trailing_stop(120.0, 120.0, 3.0, multiplier=3.0)
        assert r.stop_price is not None
        assert r.stop_price > 100.0


class TestTimeStop:
    def test_basic(self) -> None:
        from datetime import date

        r = compute_time_stop(date(2026, 6, 1), max_holding_days=60)
        assert r.time_stop_date is not None
        assert r.time_stop_date == date(2026, 7, 31)

    def test_invalid_days(self) -> None:
        r = compute_time_stop(date(2026, 6, 1), max_holding_days=0)
        assert r.time_stop_date is None
        assert "Invalid" in r.reason


class TestProfitProtection:
    def test_no_profit(self) -> None:
        r = compute_profit_protection_trail(90.0, 90.0, 100.0)
        assert r.stop_price is None
        assert "No profit" in r.reason

    def test_profit_locked(self) -> None:
        r = compute_profit_protection_trail(120.0, 120.0, 100.0, trail_pct=0.15, lock_pct=0.05)
        assert r.stop_price is not None
        assert r.stop_price >= 105.0


class TestDrawdownLadder:
    def test_no_drawdown(self) -> None:
        r = compute_drawdown_ladder(100000, 100000)
        assert r.stop_price is None

    def test_light_drawdown(self) -> None:
        r = compute_drawdown_ladder(95000, 100000)
        assert "25%" in r.reason or "reduce exposure" in r.reason

    def test_deep_drawdown(self) -> None:
        r = compute_drawdown_ladder(75000, 100000)
        assert "75%" in r.reason or "reduce exposure" in r.reason

    def test_max_drawdown(self) -> None:
        r = compute_drawdown_ladder(70000, 100000)
        assert "100%" in r.reason or "reduce exposure" in r.reason


class TestConservativeBlended:
    def test_fixed_percent_only(self) -> None:
        r = compute_conservative_blended(entry_price=100.0)
        assert r.stop_price is not None
        assert r.stop_price == 92.0  # 8% fixed stop

    def test_no_valid_stop(self) -> None:
        r = compute_conservative_blended(entry_price=0.0)
        assert r.stop_price is None


class TestRiskMethodTypes:
    def test_all_types_present(self) -> None:
        from alpha_quant.domain.risk_methods import METHOD_REGISTRY

        assert len(METHOD_REGISTRY) == 7
        assert RiskMethodType.fixed_percent.value in METHOD_REGISTRY
        assert RiskMethodType.conservative_blended.value in METHOD_REGISTRY

"""Unit tests for position sizing (domain.sizing)."""

from alpha_quant.domain.sizing import SizingConfig, size_position


def _config(**kwargs: float) -> SizingConfig:
    return SizingConfig(**kwargs)


class TestSizePosition:
    def test_zero_equity_returns_zero(self) -> None:
        result = size_position(0.0, 100.0, 2.0, 1.0, 1.0)
        assert result.shares == 0
        assert "invalid_input" in (result.capped_by or [])

    def test_zero_price_returns_zero(self) -> None:
        result = size_position(100_000.0, 0.0, 2.0, 1.0, 1.0)
        assert result.shares == 0

    def test_zero_atr_returns_zero(self) -> None:
        result = size_position(100_000.0, 100.0, 0.0, 1.0, 1.0)
        assert result.shares == 0

    def test_zero_regime_mult_returns_zero(self) -> None:
        result = size_position(100_000.0, 100.0, 2.0, 0.0, 1.0)
        assert result.shares == 0
        assert "multiplier_zero" in (result.capped_by or [])

    def test_zero_dd_mult_returns_zero(self) -> None:
        result = size_position(100_000.0, 100.0, 2.0, 1.0, 0.0)
        assert result.shares == 0

    def test_normal_sizing(self) -> None:
        result = size_position(100_000.0, 200.0, 2.0, 1.0, 1.0)
        assert result.shares > 0
        assert result.notional > 0
        assert result.risk_at_stop > 0

    def test_capped_by_max_position_pct(self) -> None:
        result = size_position(
            100_000.0,
            100.0,
            2.0,
            1.0,
            1.0,
            _config(risk_per_trade_pct=0.5, max_position_pct=0.05),
        )
        assert "max_position_pct" in (result.capped_by or [])

    def test_zero_shares_capped(self) -> None:
        result = size_position(100.0, 1_000_000.0, 2.0, 1.0, 1.0)
        assert result.shares == 0
        assert result.notional == 0.0
        assert result.risk_at_stop == 0.0

    def test_risk_at_stop_calculation(self) -> None:
        result = size_position(100_000.0, 100.0, 2.0, 1.0, 1.0)
        assert 500 < result.risk_at_stop < 700

    def test_uncapped_notional_risks_budget(self) -> None:
        result = size_position(
            100_000.0,
            200.0,
            5.0,
            1.0,
            1.0,
            _config(max_position_pct=0.5),
        )
        assert 900 < result.risk_at_stop < 1100

"""Unit tests for shadow ablation books (alpha_quant.domain.ablation)."""

import math

from alpha_quant.domain.ablation import (
    NO_CROWDING_VETO_CONFIG,
    NO_INSIDER_CONFIG,
    AblationComparison,
    AblationConfig,
    compute_ablation_comparison,
)


class TestAblationConfig:
    def test_paper_defaults(self) -> None:
        c = AblationConfig()
        assert c.disable_insider is False
        assert c.disable_crowding_veto is False

    def test_no_insider(self) -> None:
        assert NO_INSIDER_CONFIG.disable_insider is True
        assert NO_INSIDER_CONFIG.disable_crowding_veto is False

    def test_no_crowding_veto(self) -> None:
        assert NO_CROWDING_VETO_CONFIG.disable_insider is False
        assert NO_CROWDING_VETO_CONFIG.disable_crowding_veto is True

    def test_disable_both(self) -> None:
        c = AblationConfig(disable_insider=True, disable_crowding_veto=True)
        assert c.disable_insider is True
        assert c.disable_crowding_veto is True


class TestComputeAblationComparison:
    def test_returns_none_with_fewer_than_10_returns(self) -> None:
        result = compute_ablation_comparison(
            [0.01] * 5,
            [0.02] * 5,
            mechanism="NO_INSIDER",
        )
        assert result is None

    def test_returns_comparison_with_sufficient_data(self) -> None:
        paper_returns = [0.001] * 100
        ablation_returns = [0.002] * 100
        result = compute_ablation_comparison(
            paper_returns,
            ablation_returns,
            mechanism="NO_INSIDER",
        )
        assert result is not None
        assert result.mechanism == "NO_INSIDER"

    def test_higher_sharpe_is_flagged(self) -> None:
        paper_returns = [0.001, 0.002, -0.001, 0.003, -0.002] * 20
        better_returns = [0.003, 0.004, 0.001, 0.005, -0.001] * 20
        result = compute_ablation_comparison(
            paper_returns,
            better_returns,
            mechanism="NO_CROWDING_VETO",
        )
        assert result is not None
        assert result.flagged is True
        assert result.diff > 0

    def test_lower_sharpe_not_flagged(self) -> None:
        paper_returns = [0.003, 0.004, 0.001, 0.005, -0.001] * 20
        worse_returns = [0.001, 0.002, -0.001, 0.003, -0.002] * 20
        result = compute_ablation_comparison(
            paper_returns,
            worse_returns,
            mechanism="NO_INSIDER",
        )
        assert result is not None
        assert result.flagged is False
        assert result.diff < 0

    def test_equal_sharpe_not_flagged(self) -> None:
        returns = [0.001] * 100
        result = compute_ablation_comparison(
            returns,
            returns,
            mechanism="NO_INSIDER",
        )
        assert result is not None
        assert result.flagged is False
        assert result.diff == 0.0

    def test_sharpe_zero_when_no_volatility(self) -> None:
        flat = [1.0] * 100
        result = compute_ablation_comparison(flat, flat, mechanism="NO_INSIDER")
        assert result is not None
        assert math.isfinite(result.ablation_sharpe)
        assert math.isfinite(result.paper_sharpe)

    def test_comparison_rounds_to_4_decimals(self) -> None:
        paper = [0.00123456] * 100
        ablation = [0.00234567] * 100
        result = compute_ablation_comparison(
            paper,
            ablation,
            mechanism="NO_INSIDER",
        )
        assert result is not None
        assert len(str(result.paper_sharpe).split(".")[1]) <= 4
        assert len(str(result.ablation_sharpe).split(".")[1]) <= 4


class TestAblationComparison:
    def test_attributes(self) -> None:
        c = AblationComparison(
            mechanism="NO_INSIDER",
            ablation_sharpe=0.5,
            paper_sharpe=0.3,
            diff=0.2,
            flagged=True,
        )
        assert c.mechanism == "NO_INSIDER"
        assert c.ablation_sharpe == 0.5
        assert c.paper_sharpe == 0.3
        assert c.diff == 0.2
        assert c.flagged is True

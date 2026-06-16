"""Unit tests for M4 fundamental quality gate (domain.fundamental)."""

from domain.fundamental import QualityVerdict, evaluate
from tests.conftest import make_earnings, make_fundamentals


class TestEvaluate:
    def test_all_missing_passes_degraded(self) -> None:
        f = make_fundamentals(
            ocf=None,
            total_liabilities=None,
            total_debt=None,
            total_equity=None,
            net_income=None,
            accruals=None,
        )
        result = evaluate(f)
        assert result.passed is True
        assert result.passed_degraded is True

    def test_positive_ocf_passes(self) -> None:
        f = make_fundamentals(ocf=100_000_000_000.0)
        result = evaluate(f)
        assert result.passed is True

    def test_zero_ocf_fails(self) -> None:
        f = make_fundamentals(ocf=0.0)
        result = evaluate(f)
        assert result.passed is False
        assert "operating_cash_flow" in result.reason

    def test_negative_ocf_fails(self) -> None:
        f = make_fundamentals(ocf=-5_000_000_000.0)
        result = evaluate(f)
        assert result.passed is False
        assert "operating_cash_flow" in result.reason

    def test_de_below_threshold_passes(self) -> None:
        f = make_fundamentals(total_debt=50_000_000_000.0, total_equity=200_000_000_000.0)
        result = evaluate(f, sector_median_de=1.5)
        assert result.passed is True

    def test_de_above_threshold_fails(self) -> None:
        f = make_fundamentals(total_debt=400_000_000_000.0, total_equity=100_000_000_000.0)
        result = evaluate(f, sector_median_de=1.5)
        assert result.passed is False
        assert "D/E" in result.reason

    def test_de_skipped_when_no_median(self) -> None:
        f = make_fundamentals(total_debt=400_000_000_000.0, total_equity=100_000_000_000.0)
        result = evaluate(f, sector_median_de=None)
        assert result.passed is True

    def test_accrual_ratio_within_range_passes(self) -> None:
        f = make_fundamentals(
            accruals=5_000_000_000.0,
            total_debt=100_000_000_000.0,
            total_equity=200_000_000_000.0,
        )
        result = evaluate(f)
        assert result.passed is True

    def test_accrual_ratio_above_range_fails(self) -> None:
        f = make_fundamentals(
            accruals=50_000_000_000.0,
            total_debt=100_000_000_000.0,
            total_equity=200_000_000_000.0,
        )
        result = evaluate(f)
        assert result.passed is False
        assert "accrual" in result.reason

    def test_negative_earnings_surprise_fails(self) -> None:
        f = make_fundamentals()
        result = evaluate(f, recent_earnings=make_earnings(eps_estimate=1.0, eps_actual=0.5))
        assert result.passed is False
        assert "earnings surprise" in result.reason

    def test_positive_earnings_surprise_passes(self) -> None:
        f = make_fundamentals()
        result = evaluate(f, recent_earnings=make_earnings(eps_estimate=1.0, eps_actual=1.20))
        assert result.passed is True

    def test_multiple_failures_combined(self) -> None:
        f = make_fundamentals(
            ocf=-1.0,
            total_debt=500.0,
            total_equity=1.0,
            accruals=100.0,
        )
        result = evaluate(
            f,
            sector_median_de=0.5,
            recent_earnings=make_earnings(eps_estimate=1.0, eps_actual=0.5),
        )
        assert result.passed is False
        assert ";" in result.reason

    def test_accrual_skipped_when_liabilities_missing(self) -> None:
        f = make_fundamentals(
            total_liabilities=None,
            total_debt=100_000_000_000.0,
            total_equity=200_000_000_000.0,
            accruals=50_000_000_000.0,
        )
        result = evaluate(f)
        assert result.passed is True
        assert result.passed_degraded is True
        assert "accrual" in result.reason.lower()

    def test_accrual_computed_with_liabilities(self) -> None:
        f = make_fundamentals(
            total_liabilities=300_000_000_000.0,
            total_equity=200_000_000_000.0,
            accruals=50_000_000_000.0,
        )
        result = evaluate(f)
        assert result.passed is False
        assert "accrual" in result.reason

    def test_quality_verdict_repr(self) -> None:
        v = QualityVerdict(passed=True)
        assert "passed=True" in repr(v)

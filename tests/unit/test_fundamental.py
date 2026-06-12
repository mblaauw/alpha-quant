"""Unit tests for M4 fundamental quality gate (alpha_quant.domain.fundamental)."""

from datetime import date

from alpha_quant.domain.fundamental import QualityVerdict, evaluate
from alpha_quant.domain.models import EarningsEntry, FundamentalsSnapshot


def _fundamentals(**kwargs: float | None) -> FundamentalsSnapshot:
    return FundamentalsSnapshot(
        symbol="AAPL",
        as_of_date=date(2026, 6, 11),
        market_cap=kwargs.get("market_cap", 3_000_000_000_000.0),
        operating_cash_flow=kwargs.get("ocf", 100_000_000_000.0),
        total_debt=kwargs.get("total_debt", 50_000_000_000.0),
        total_equity=kwargs.get("total_equity", 200_000_000_000.0),
        net_income=kwargs.get("net_income", 50_000_000_000.0),
        accruals=kwargs.get("accruals", 0.0),
    )


def _earnings(estimate: float, actual: float) -> EarningsEntry:
    return EarningsEntry(
        symbol="AAPL",
        date=date(2026, 6, 11),
        eps_estimate=estimate,
        eps_actual=actual,
    )


class TestEvaluate:
    def test_all_missing_passes_degraded(self) -> None:
        f = _fundamentals(
            ocf=None,
            total_debt=None,
            total_equity=None,
            net_income=None,
            accruals=None,
        )
        result = evaluate(f)
        assert result.passed is True
        assert result.passed_degraded is True

    def test_positive_ocf_passes(self) -> None:
        f = _fundamentals(ocf=100_000_000_000.0)
        result = evaluate(f)
        assert result.passed is True

    def test_zero_ocf_fails(self) -> None:
        f = _fundamentals(ocf=0.0)
        result = evaluate(f)
        assert result.passed is False
        assert "operating_cash_flow" in result.reason

    def test_negative_ocf_fails(self) -> None:
        f = _fundamentals(ocf=-5_000_000_000.0)
        result = evaluate(f)
        assert result.passed is False
        assert "operating_cash_flow" in result.reason

    def test_de_below_threshold_passes(self) -> None:
        f = _fundamentals(total_debt=50_000_000_000.0, total_equity=200_000_000_000.0)
        result = evaluate(f, sector_median_de=1.5)
        assert result.passed is True

    def test_de_above_threshold_fails(self) -> None:
        f = _fundamentals(total_debt=400_000_000_000.0, total_equity=100_000_000_000.0)
        result = evaluate(f, sector_median_de=1.5)
        assert result.passed is False
        assert "D/E" in result.reason

    def test_de_skipped_when_no_median(self) -> None:
        f = _fundamentals(total_debt=400_000_000_000.0, total_equity=100_000_000_000.0)
        result = evaluate(f, sector_median_de=None)
        assert result.passed is True

    def test_accrual_ratio_within_range_passes(self) -> None:
        f = _fundamentals(
            accruals=5_000_000_000.0,
            total_debt=100_000_000_000.0,
            total_equity=200_000_000_000.0,
        )
        result = evaluate(f)
        assert result.passed is True

    def test_accrual_ratio_above_range_fails(self) -> None:
        f = _fundamentals(
            accruals=50_000_000_000.0,
            total_debt=100_000_000_000.0,
            total_equity=200_000_000_000.0,
        )
        result = evaluate(f)
        assert result.passed is False
        assert "accrual" in result.reason

    def test_negative_earnings_surprise_fails(self) -> None:
        f = _fundamentals()
        result = evaluate(f, recent_earnings=_earnings(estimate=1.0, actual=0.5))
        assert result.passed is False
        assert "earnings surprise" in result.reason

    def test_positive_earnings_surprise_passes(self) -> None:
        f = _fundamentals()
        result = evaluate(f, recent_earnings=_earnings(estimate=1.0, actual=1.20))
        assert result.passed is True

    def test_multiple_failures_combined(self) -> None:
        f = _fundamentals(
            ocf=-1.0,
            total_debt=500.0,
            total_equity=1.0,
            accruals=100.0,
        )
        result = evaluate(
            f,
            sector_median_de=0.5,
            recent_earnings=_earnings(estimate=1.0, actual=0.5),
        )
        assert result.passed is False
        assert ";" in result.reason

    def test_quality_verdict_repr(self) -> None:
        v = QualityVerdict(passed=True)
        assert "passed=True" in repr(v)

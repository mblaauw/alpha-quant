"""Fundamental quality evaluation (accrual, D/E, cash flow)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from domain.models import EarningsEntry, FundamentalsSnapshot


class QualityVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)
    passed: bool
    passed_degraded: bool = False
    reason: str = ""


def evaluate(
    fundamentals: FundamentalsSnapshot,
    sector_median_de: float | None = None,
    recent_earnings: EarningsEntry | None = None,
    accrual_threshold: float = 0.05,
) -> QualityVerdict:
    if _all_missing(fundamentals):
        return QualityVerdict(passed=True, passed_degraded=True, reason="no fundamentals data")

    failures: list[str] = []

    ocf = fundamentals.operating_cash_flow
    if ocf is not None and ocf <= 0:
        failures.append("operating_cash_flow <= 0")

    de = _compute_de(fundamentals)
    if (
        de is not None
        and sector_median_de is not None
        and sector_median_de > 0
        and de >= sector_median_de * 2
    ):
        failures.append(f"D/E ({de:.2f}) >= sector median * 2")

    accrual_ratio = _compute_accrual_ratio(fundamentals)
    accrual_skipped = False
    if accrual_ratio is not None and (
        accrual_ratio < -accrual_threshold or accrual_ratio > accrual_threshold
    ):
        failures.append(
            f"accrual ratio ({accrual_ratio:.4f}) outside"
            f" [-{accrual_threshold:.2f}, {accrual_threshold:.2f}]"
        )
    elif (
        accrual_ratio is None
        and fundamentals.total_liabilities is None
        and fundamentals.accruals is not None
    ):
        accrual_skipped = True

    if recent_earnings is not None:
        surprise = _check_negative_surprise(recent_earnings)
        if surprise is not None:
            failures.append(surprise)

    if failures:
        return QualityVerdict(passed=False, reason="; ".join(failures))

    if accrual_skipped:
        return QualityVerdict(
            passed=True,
            passed_degraded=True,
            reason="accrual check skipped (missing total_liabilities)",
        )

    return QualityVerdict(passed=True)


def _compute_de(fundamentals: FundamentalsSnapshot) -> float | None:
    if fundamentals.total_debt is None or fundamentals.total_equity is None:
        return None
    if fundamentals.total_equity == 0:
        return None
    return fundamentals.total_debt / fundamentals.total_equity


def _compute_accrual_ratio(fundamentals: FundamentalsSnapshot) -> float | None:
    accruals = fundamentals.accruals
    if accruals is None:
        return None
    assets = _estimate_total_assets(fundamentals)
    if assets is None or assets == 0:
        return None
    return accruals / assets


def _estimate_total_assets(fundamentals: FundamentalsSnapshot) -> float | None:
    if fundamentals.total_liabilities is not None and fundamentals.total_equity is not None:
        return fundamentals.total_liabilities + fundamentals.total_equity
    return None


def _check_negative_surprise(earnings: EarningsEntry) -> str | None:
    if earnings.eps_estimate is None or earnings.eps_actual is None:
        return None
    if earnings.eps_estimate == 0:
        return None
    surprise_pct = (earnings.eps_actual - earnings.eps_estimate) / abs(earnings.eps_estimate)
    if surprise_pct < -0.10:
        return f"negative earnings surprise ({surprise_pct * 100:.1f}%)"
    return None


def _all_missing(fundamentals: FundamentalsSnapshot) -> bool:
    return all(
        v is None
        for v in [
            fundamentals.operating_cash_flow,
            fundamentals.total_liabilities,
            fundamentals.total_debt,
            fundamentals.total_equity,
            fundamentals.net_income,
            fundamentals.accruals,
        ]
    )

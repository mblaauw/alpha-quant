"""Validation rules for bars and indicator states."""

from __future__ import annotations

from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from domain.calendar import next_market_day
from domain.models import Bar, FundamentalsSnapshot, IndicatorState

_isnan = np.isnan
_isinf = np.isinf
_ISSUE_PREVIEW = 3


class ValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    is_valid: bool
    check: str = ""
    issues: list[str] = Field(default_factory=list)
    severity: str = "WARN"


def _nan_inf_issues(val: Any, name: str) -> list[str]:
    issues: list[str] = []
    if val is None:
        issues.append(f"{name} is None")
    elif _isnan(val) or _isinf(val):
        issues.append(f"{name} is NaN or Inf")
    return issues


def validate_bars(
    bars: list[Bar],
    spike_atr_mult: float = 5.0,
) -> list[ValidationResult]:
    results: list[ValidationResult] = []

    bad_prices: list[str] = []
    bad_volumes: list[str] = []
    volume_spikes: list[str] = []
    volume_drops: list[str] = []
    nan_issues: list[str] = []
    return_spikes: list[str] = []
    date_gaps: list[str] = []

    for i, bar in enumerate(bars):
        for field, field_name in [
            (bar.open, "open"),
            (bar.high, "high"),
            (bar.low, "low"),
            (bar.close, "close"),
            (bar.volume, "volume"),
        ]:
            ni = _nan_inf_issues(field, field_name)
            if ni:
                nan_issues.extend(ni)
            if field is not None and field <= 0:
                bad_prices.append(f"{field_name}={field} on {bar.date}")

        if bar.volume is not None and bar.volume <= 0:
            bad_volumes.append(str(bar.date))
        elif bar.volume is not None and i > 0:
            prev_vol = bars[i - 1].volume
            if prev_vol is not None and prev_vol > 0 and bar.volume > prev_vol * 10:
                volume_spikes.append(f"{bar.date} vol={bar.volume:.0f} x10 vs prev={prev_vol:.0f}")

        if i >= 20:
            window = bars[i - 19 : i + 1]
            vols = [b.volume for b in window if b.volume is not None and b.volume > 0]
            if len(vols) >= 5 and bar.volume is not None:
                avg_vol = sum(vols) / len(vols)
                if bar.volume < avg_vol * 0.1:
                    volume_drops.append(
                        f"{bar.date} vol={bar.volume:.0f} <10% of 20d avg={avg_vol:.0f}"
                    )  # noqa: E501

        if i > 0:
            prev = bars[i - 1]
            if prev.close is not None and prev.close > 0 and bar.close is not None:
                ret = abs(bar.close / prev.close - 1.0)
                window = bars[max(0, i - 20) : i]
                closes = [b.close for b in window if b.close is not None and b.close > 0]
                if closes:
                    returns = [abs(closes[j] / closes[j - 1] - 1.0) for j in range(1, len(closes))]
                    avg_ret = sum(returns) / len(returns) if returns else 0.01
                    threshold = min(max(avg_ret * spike_atr_mult, 0.05), 1.0)
                else:
                    threshold = 0.4
                if ret > threshold:
                    return_spikes.append(
                        f"{bar.date} return={ret * 100:.1f}% (threshold={threshold * 100:.1f}%)"
                    )  # noqa: E501

            gap = (bar.date - prev.date).days
            expected_next = next_market_day(prev.date)
            expected_gap = (expected_next - prev.date).days
            if gap > expected_gap + 1:
                date_gaps.append(f"{prev.date} to {bar.date} ({gap}d, expected {expected_gap}d)")

    if nan_issues:
        results.append(
            ValidationResult(
                is_valid=False,
                check="bar_nan_inf",
                issues=nan_issues[:_ISSUE_PREVIEW],
                severity="QUARANTINE",
            )
        )
    if bad_prices:
        results.append(
            ValidationResult(
                is_valid=False,
                check="bar_price_sanity",
                issues=bad_prices[:_ISSUE_PREVIEW],
                severity="QUARANTINE",
            )
        )
    if return_spikes:
        results.append(
            ValidationResult(
                is_valid=False,
                check="bar_return_spike",
                issues=return_spikes[:_ISSUE_PREVIEW],
                severity="QUARANTINE",
            )
        )
    if bad_volumes:
        results.append(
            ValidationResult(
                is_valid=False,
                check="bar_zero_volume",
                issues=bad_volumes[:_ISSUE_PREVIEW],
                severity="WARN",
            )
        )
    if volume_spikes:
        results.append(
            ValidationResult(
                is_valid=False,
                check="bar_volume_spike",
                issues=volume_spikes[:_ISSUE_PREVIEW],
                severity="WARN",
            )
        )
    if volume_drops:
        results.append(
            ValidationResult(
                is_valid=False,
                check="bar_volume_drop",
                issues=volume_drops[:_ISSUE_PREVIEW],
                severity="WARN",
            )
        )
    if date_gaps:
        results.append(
            ValidationResult(
                is_valid=False,
                check="bar_date_gap",
                issues=date_gaps[:_ISSUE_PREVIEW],
                severity="WARN",
            )
        )

    return results


def validate_fundamentals(snapshot: FundamentalsSnapshot) -> list[ValidationResult]:
    results: list[ValidationResult] = []

    issues: list[str] = []
    for field, field_name in [
        (snapshot.market_cap, "market_cap"),
        (snapshot.pe_ratio, "pe_ratio"),
        (snapshot.eps_ttm, "eps_ttm"),
        (snapshot.dividend_yield, "dividend_yield"),
        (snapshot.operating_cash_flow, "operating_cash_flow"),
        (snapshot.total_liabilities, "total_liabilities"),
        (snapshot.total_debt, "total_debt"),
        (snapshot.total_equity, "total_equity"),
        (snapshot.revenue, "revenue"),
        (snapshot.net_income, "net_income"),
    ]:
        if field is not None and (_isnan(field) or _isinf(field)):
            issues.append(f"{field_name} is NaN/Inf")

    if snapshot.market_cap is not None and snapshot.market_cap <= 0:
        issues.append(f"market_cap <= 0 ({snapshot.market_cap})")
    if snapshot.total_debt is not None and snapshot.total_debt < 0:
        issues.append(f"total_debt < 0 ({snapshot.total_debt})")
    if snapshot.total_liabilities is not None and snapshot.total_liabilities < 0:
        issues.append(f"total_liabilities < 0 ({snapshot.total_liabilities})")

    if issues:
        results.append(
            ValidationResult(
                is_valid=False,
                check="fundamentals_schema",
                issues=issues,
                severity="QUARANTINE",
            )
        )

    return results


def validate_indicator_state(state: IndicatorState) -> list[ValidationResult]:
    results: list[ValidationResult] = []

    nan_keys: list[str] = []
    for key, value in state.values.items():
        if value is None or _isnan(value) or _isinf(value):
            nan_keys.append(key)

    if nan_keys:
        results.append(
            ValidationResult(
                is_valid=False,
                check="indicator_nan",
                issues=[f"{state.symbol}: NaN/Inf in {', '.join(nan_keys)}"],
                severity="QUARANTINE",
            )
        )

    rsi = state.values.get("rsi")
    if rsi is not None and not _isnan(rsi) and not _isinf(rsi) and (rsi < 0.0 or rsi > 100.0):
        results.append(
            ValidationResult(
                is_valid=False,
                check="indicator_rsi_range",
                issues=[f"{state.symbol} RSI={rsi} outside [0, 100]"],
                severity="QUARANTINE",
            )
        )

    return results

from __future__ import annotations

from typing import Literal

from alpha_quant.domain.decision_context import DecisionContext

Regime = Literal["RISK_ON", "CAUTION", "RISK_OFF"]

REGIME_MULTIPLIERS: dict[Regime, float] = {
    "RISK_ON": 1.0,
    "CAUTION": 0.5,
    "RISK_OFF": 0.0,
}

RISK_ON: Regime = "RISK_ON"
CAUTION: Regime = "CAUTION"
RISK_OFF: Regime = "RISK_OFF"

_EMA200_WARMUP_BARS = 200


def detect(
    context: DecisionContext,
    vix_level: float | None = None,
    breadth: float | None = None,
) -> Regime:
    spy_close = context.latest_close()
    spy_ema50 = context.indicator("trend.ma_regime_50")
    spy_ema200 = context.indicator("trend.ma_regime_200")
    bar_count = len(context.bars)

    if spy_close is None or spy_ema50 is None or spy_ema200 is None:
        return CAUTION

    ema200_warm = bar_count >= _EMA200_WARMUP_BARS

    if spy_close <= spy_ema50:
        if not ema200_warm:
            return CAUTION
        if breadth is not None and breadth <= 0.2:
            return _check_risk_off(spy_close, spy_ema200, vix_level)
        return _check_risk_off(spy_close, spy_ema200, vix_level)

    if spy_ema50 <= spy_ema200:
        if not ema200_warm:
            return CAUTION
        if breadth is not None and breadth <= 0.2:
            return _check_risk_off(spy_close, spy_ema200, vix_level)
        return _check_risk_off(spy_close, spy_ema200, vix_level)

    if vix_level is not None and vix_level >= 20:
        if not ema200_warm:
            return CAUTION
        return _check_risk_off(spy_close, spy_ema200, vix_level)

    if breadth is not None and breadth <= 0.2:
        if not ema200_warm:
            return CAUTION
        return _check_risk_off(spy_close, spy_ema200, vix_level)
    if breadth is not None and breadth <= 0.4:
        return CAUTION

    return RISK_ON


def _check_risk_off(
    spy_close: float,
    spy_ema200: float,
    vix_level: float | None,
) -> Regime:
    if spy_close < spy_ema200:
        return RISK_OFF
    if vix_level is not None and vix_level > 30:
        return RISK_OFF
    return CAUTION

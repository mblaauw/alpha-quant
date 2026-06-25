from __future__ import annotations

from alpha_quant.domain.decision_context import DecisionContext


def evaluate(context: DecisionContext) -> float:
    rsi = context.indicator("momentum.rsi_14")
    macd_hist = context.indicator("trend.macd_histogram")
    atr_pct = context.indicator("volatility.atr_pct_14")
    close = context.latest_close()

    if close is None:
        return 0.0

    trend_s = _trend_score(close, context)
    rsi_s = _rsi_score(rsi)
    macd_s = _macd_score(macd_hist)
    volume_s = _volume_score(context)
    atr_s = _atr_score(close, atr_pct)

    weights = {
        "trend": 0.3125,
        "rsi": 0.25,
        "macd": 0.1875,
        "volume": 0.125,
        "atr": 0.125,
    }

    composite = (
        trend_s * weights["trend"]
        + rsi_s * weights["rsi"]
        + macd_s * weights["macd"]
        + volume_s * weights["volume"]
        + atr_s * weights["atr"]
    )

    return round(max(0.0, min(1.0, composite)), 4)


def momentum_score(context: DecisionContext) -> float:
    return_63d = context.indicator("momentum.return_63d")
    if return_63d is None:
        return 0.3
    if return_63d > 0.20:
        return 1.0
    if return_63d > 0.10:
        return 0.8
    if return_63d > 0.05:
        return 0.6
    if return_63d < -0.10:
        return 0.0
    if return_63d < -0.05:
        return 0.2
    return 0.4


def _trend_score(close: float, context: DecisionContext) -> float:
    ma_regime = context.indicator("trend.ma_regime_50")
    if ma_regime is None or ma_regime <= 0:
        return 0.0
    ratio = close / ma_regime
    if ratio >= 1.05:
        return 1.0
    if ratio >= 1.0:
        return 0.6
    if ratio >= 0.95:
        return 0.3
    return 0.0


def _rsi_score(rsi: float | None) -> float:
    if rsi is None:
        return 0.3
    if rsi >= 70:
        return 0.0
    if rsi >= 60:
        return 0.3
    if rsi >= 40:
        return 0.6
    if rsi >= 30:
        return 0.3
    return 0.0


def _macd_score(macd_hist: float | None) -> float:
    if macd_hist is None:
        return 0.3
    if macd_hist > 0:
        return 0.8
    return 0.2


def _volume_score(context: DecisionContext) -> float:
    vol_ratio = context.indicator("liquidity.volume_ratio_21")
    if vol_ratio is None:
        return 0.5
    if vol_ratio > 2.0:
        return 0.2
    if vol_ratio > 1.5:
        return 0.6
    if vol_ratio > 0.5:
        return 0.8
    return 0.3


def _atr_score(close: float, atr_pct: float | None) -> float:
    if atr_pct is None or atr_pct <= 0:
        return 0.5
    if atr_pct > 0.04:
        return 0.0
    if atr_pct > 0.025:
        return 0.3
    if atr_pct > 0.015:
        return 0.6
    return 0.8

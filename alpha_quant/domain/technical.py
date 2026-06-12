from __future__ import annotations

import numpy as np

from alpha_quant.domain.models import Bar, IndicatorState

_isnan = np.isnan


class TechnicalScore:
    def __init__(self, score: float) -> None:
        self.score = score

    def __repr__(self) -> str:
        return f"TechnicalScore(score={self.score:.4f})"


def score(bars: list[Bar], indicator: IndicatorState) -> TechnicalScore:
    vals = indicator.values
    close = vals.get("prev_close")

    if close is None or _isnan(close):
        return TechnicalScore(0.0)

    weights = {
        "trend": 0.25,
        "momentum": 0.20,
        "rsi": 0.20,
        "macd": 0.15,
        "volume": 0.10,
        "atr": 0.10,
    }

    trend_s = _trend_score(close, vals)
    momentum_s = _momentum_score(bars, close)
    rsi_s = _rsi_score(vals)
    macd_s = _macd_score(vals)
    volume_s = _volume_score(bars)
    atr_s = _atr_score(close, vals)

    composite = (
        trend_s * weights["trend"]
        + momentum_s * weights["momentum"]
        + rsi_s * weights["rsi"]
        + macd_s * weights["macd"]
        + volume_s * weights["volume"]
        + atr_s * weights["atr"]
    )

    return TechnicalScore(round(max(0.0, min(1.0, composite)), 4))


def _trend_score(close: float, vals: dict[str, float]) -> float:
    ema50 = vals.get("ema50")
    if ema50 is None or _isnan(ema50) or ema50 <= 0:
        return 0.0
    ratio = close / ema50
    if ratio >= 1.05:
        return 1.0
    if ratio >= 1.0:
        return 0.6
    if ratio >= 0.95:
        return 0.3
    return 0.0


def _momentum_score(bars: list[Bar], close: float) -> float:
    n = len(bars)
    if n < 2:
        return 0.3

    lookback = min(63, n - 1)
    prev_close = bars[-(lookback + 1)].close
    if prev_close <= 0:
        return 0.0

    ret = (close - prev_close) / prev_close
    if ret > 0.20:
        return 1.0
    if ret > 0.10:
        return 0.8
    if ret > 0.05:
        return 0.6
    if ret > 0.0:
        return 0.5
    if ret > -0.05:
        return 0.3
    if ret > -0.15:
        return 0.1
    return 0.0


def _rsi_score(vals: dict[str, float]) -> float:
    rsi = vals.get("rsi")
    if rsi is None or _isnan(rsi):
        return 0.3
    if 45.0 <= rsi <= 70.0:
        return 1.0
    if 40.0 <= rsi <= 75.0:
        return 0.7
    if 30.0 <= rsi <= 80.0:
        return 0.4
    return 0.1


def _macd_score(vals: dict[str, float]) -> float:
    hist = vals.get("macd_histogram")
    if hist is None or _isnan(hist):
        return 0.3
    if hist > 0:
        return 1.0
    return 0.0


def _volume_score(bars: list[Bar]) -> float:
    n = len(bars)
    if n < 2:
        return 0.5
    current = bars[-1].volume
    if current <= 0:
        return 0.0
    avg = sum(b.volume for b in bars[:-1]) / (n - 1)
    if avg <= 0:
        return 0.5
    ratio = current / avg
    if ratio >= 1.5:
        return 1.0
    if ratio >= 1.0:
        return 0.7
    if ratio >= 0.7:
        return 0.4
    return 0.2


def _atr_score(close: float, vals: dict[str, float]) -> float:
    atr = vals.get("atr")
    if atr is None or _isnan(atr) or atr <= 0 or close <= 0:
        return 0.5
    pct = atr / close
    if pct <= 0.01:
        return 1.0
    if pct <= 0.02:
        return 0.8
    if pct <= 0.03:
        return 0.5
    if pct <= 0.05:
        return 0.2
    return 0.0

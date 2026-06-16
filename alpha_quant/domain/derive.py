"""Incremental indicator computation (EMA, RSI, ATR, MACD)."""

from __future__ import annotations

from datetime import date

import numpy as np

from alpha_quant.domain.models import Bar, IndicatorState

_isnan = np.isnan

_ALPHA_12 = 2.0 / (12.0 + 1.0)
_ALPHA_20 = 2.0 / (20.0 + 1.0)
_ALPHA_26 = 2.0 / (26.0 + 1.0)
_ALPHA_50 = 2.0 / (50.0 + 1.0)
_ALPHA_200 = 2.0 / (200.0 + 1.0)
_ALPHA_9 = 2.0 / (9.0 + 1.0)
_RSI_PERIOD = 14
_RSI_ALPHA = 1.0 / _RSI_PERIOD
_ATR_PERIOD = 14
_ATR_ALPHA = 1.0 / _ATR_PERIOD


def _empty_state(symbol: str, dt: date) -> dict[str, float]:
    return {
        "ema12": np.nan,
        "ema20": np.nan,
        "ema26": np.nan,
        "ema50": np.nan,
        "ema200": np.nan,
        "macd_line": np.nan,
        "macd_signal": np.nan,
        "macd_histogram": np.nan,
        "rsi_avg_gain": np.nan,
        "rsi_avg_loss": np.nan,
        "rsi": np.nan,
        "atr": np.nan,
        "processed_close": np.nan,
        "bar_count": 0,
    }


def _update_ema(prev: float, value: float, alpha: float) -> float:
    if _isnan(prev):
        return value
    return value * alpha + prev * (1.0 - alpha)


def _update_rsi(
    avg_gain: float, avg_loss: float, price: float, prev_close: float
) -> tuple[float, float, float]:
    change = price - prev_close
    gain = change if change > 0.0 else 0.0
    loss = -change if change < 0.0 else 0.0

    if _isnan(avg_gain) or _isnan(avg_loss):
        return gain, loss, 50.0

    new_avg_gain = gain * _RSI_ALPHA + avg_gain * (1.0 - _RSI_ALPHA)
    new_avg_loss = loss * _RSI_ALPHA + avg_loss * (1.0 - _RSI_ALPHA)

    if new_avg_loss == 0.0:
        rsi = 100.0
    else:
        rs = new_avg_gain / new_avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))

    return new_avg_gain, new_avg_loss, rsi


def _update_atr(prev_atr: float, high: float, low: float, prev_close: float) -> float:
    hl = high - low
    hc = abs(high - prev_close)
    lc = abs(low - prev_close)
    tr = hl if hl >= hc and hl >= lc else (hc if hc >= lc else lc)
    if _isnan(prev_atr):
        return tr
    return tr * _ATR_ALPHA + prev_atr * (1.0 - _ATR_ALPHA)


def update_indicator_state(state: IndicatorState, bar: Bar) -> IndicatorState:
    src = state.values
    price = float(bar.close)

    e12 = _update_ema(src["ema12"], price, _ALPHA_12)
    e20 = _update_ema(src["ema20"], price, _ALPHA_20)
    e26 = _update_ema(src["ema26"], price, _ALPHA_26)
    e50 = _update_ema(src["ema50"], price, _ALPHA_50)
    e200 = _update_ema(src["ema200"], price, _ALPHA_200)

    m_line = e12 - e26
    m_sig = _update_ema(src["macd_signal"], m_line, _ALPHA_9)
    m_hist = m_line - m_sig

    bc = src.get("bar_count", 0.0) + 1.0

    pc = src["processed_close"]
    if not _isnan(pc):
        ra_g, ra_l, rsi = _update_rsi(src["rsi_avg_gain"], src["rsi_avg_loss"], price, pc)
        atr = _update_atr(src["atr"], bar.high, bar.low, pc)
    else:
        ra_g, ra_l, rsi = src["rsi_avg_gain"], src["rsi_avg_loss"], src["rsi"]
        atr = src["atr"]

    v: dict[str, float] = {
        "ema12": e12,
        "ema20": e20,
        "ema26": e26,
        "ema50": e50,
        "ema200": e200,
        "macd_line": m_line,
        "macd_signal": m_sig,
        "macd_histogram": m_hist,
        "rsi_avg_gain": ra_g,
        "rsi_avg_loss": ra_l,
        "rsi": rsi,
        "atr": atr,
        "processed_close": price,
        "bar_count": bc,
    }

    return IndicatorState(symbol=state.symbol, date=bar.date, values=v)


def backfill_indicator_state(bars: list[Bar]) -> IndicatorState:
    if not bars:
        raise ValueError("backfill requires at least one bar")

    symbol = bars[0].symbol
    dt = bars[0].date
    state = IndicatorState(symbol=symbol, date=dt, values=_empty_state(symbol, dt))

    for bar in bars:
        state = update_indicator_state(state, bar)

    return state


def _bruteforce_ema(values: np.ndarray, period: int) -> np.ndarray:
    alpha = 2.0 / (period + 1.0)
    ema = np.full(len(values), np.nan)
    ema[0] = values[0]
    for i in range(1, len(values)):
        if _isnan(values[i]):
            continue
        ema[i] = values[i] * alpha + ema[i - 1] * (1.0 - alpha)
    return ema


def _bruteforce_rsi(close_prices: np.ndarray) -> np.ndarray:
    changes = np.diff(close_prices)
    gains = np.where(changes > 0.0, changes, 0.0)
    losses = np.where(changes < 0.0, -changes, 0.0)

    rsi = np.full(len(close_prices), np.nan)
    rsi[0] = 50.0

    avg_gain = gains[0] if len(gains) > 0 else 0.0
    avg_loss = losses[0] if len(losses) > 0 else 0.0

    for i in range(len(gains)):
        avg_gain = gains[i] * _RSI_ALPHA + avg_gain * (1.0 - _RSI_ALPHA)
        avg_loss = losses[i] * _RSI_ALPHA + avg_loss * (1.0 - _RSI_ALPHA)
        if avg_loss == 0.0:
            rsi[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i + 1] = 100.0 - (100.0 / (1.0 + rs))

    return rsi


def _bruteforce_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    hl = high - low
    hc = np.abs(high - np.roll(close, 1))
    lc = np.abs(low - np.roll(close, 1))
    hc[0] = 0.0
    lc[0] = 0.0
    tr = np.maximum(np.maximum(hl, hc), lc)

    atr = np.full(len(close), np.nan)
    atr[0] = tr[0]

    for i in range(1, len(close)):
        atr[i] = tr[i] * _ATR_ALPHA + atr[i - 1] * (1.0 - _ATR_ALPHA)

    return atr


def _build_incremental_series(bars: list[Bar]) -> dict[str, np.ndarray]:
    if not bars:
        return {}
    n = len(bars)
    keys = [
        "ema12",
        "ema20",
        "ema26",
        "ema50",
        "ema200",
        "macd_line",
        "macd_signal",
        "macd_histogram",
        "rsi",
        "atr",
    ]
    series: dict[str, np.ndarray] = {k: np.full(n, np.nan) for k in keys}
    symbol = bars[0].symbol
    state = IndicatorState(
        symbol=symbol, date=bars[0].date, values=_empty_state(symbol, bars[0].date)
    )
    for i, bar in enumerate(bars):
        state = update_indicator_state(state, bar)
        for k in keys:
            val = state.values.get(k)
            if val is not None and not np.isnan(val):
                series[k][i] = val
    return series


_VERIFY_KEYS = [
    ("ema20", 20),
    ("ema50", 50),
    ("ema200", 200),
    ("rsi", None),
    ("atr", None),
    ("macd_line", None),
    ("macd_signal", None),
    ("macd_histogram", None),
]

# Reference fixture: 30-bar triangular price series for external validation.
# Generated by: step up from 10.0 to 17.5 in 0.5 increments, then back down.
# Reference EMA20/RSI14/ATR14 computed using the exact Derive engine formulas
# (EMA seeded to first close, RSI seeded to (gain,loss,50.0), ATR seeded to TR[0]).
# These are the ground-truth values the incremental engine must reproduce.
# See P2.RK ADR-0022 for methodology.
_REF_INPUT: dict[str, list[float]] = {
    "close": [
        10.0,
        10.5,
        11.0,
        11.5,
        12.0,
        12.5,
        13.0,
        13.5,
        14.0,
        14.5,
        15.0,
        15.5,
        16.0,
        16.5,
        17.0,
        17.0,
        16.5,
        16.0,
        15.5,
        15.0,
        14.5,
        14.0,
        13.5,
        13.0,
        12.5,
        12.0,
        11.5,
        11.0,
        10.5,
        10.0,
    ],
    "high": [
        10.5,
        11.0,
        11.5,
        12.0,
        12.5,
        13.0,
        13.5,
        14.0,
        14.5,
        15.0,
        15.5,
        16.0,
        16.5,
        17.0,
        17.5,
        17.5,
        17.0,
        16.5,
        16.0,
        15.5,
        15.0,
        14.5,
        14.0,
        13.5,
        13.0,
        12.5,
        12.0,
        11.5,
        11.0,
        10.5,
    ],
    "low": [
        9.5,
        10.0,
        10.5,
        11.0,
        11.5,
        12.0,
        12.5,
        13.0,
        13.5,
        14.0,
        14.5,
        15.0,
        15.5,
        16.0,
        16.5,
        16.5,
        16.0,
        15.5,
        15.0,
        14.5,
        14.0,
        13.5,
        13.0,
        12.5,
        12.0,
        11.5,
        11.0,
        10.5,
        10.0,
        9.5,
    ],
}

_REF_EXPECTED: dict[str, list[float | None]] = {
    "ema20": [
        10.0,
        10.0476190476,
        10.1383219955,
        10.2680056149,
        10.4329574611,
        10.6298186553,
        10.855550212,
        11.1074025727,
        11.382888042,
        11.6797558475,
        11.9959695763,
        12.3296867595,
        12.6792404015,
        13.043122268,
        13.4199677663,
        13.7609232171,
        14.0217876726,
        14.2101888467,
        14.3330280041,
        14.3965491466,
        14.4064016088,
        14.3676966937,
        14.2850589133,
        14.1626723502,
        14.0043226025,
        13.8134347356,
        13.5931076179,
        13.3461449877,
        13.0750835603,
        12.7822184593,
    ],
    "rsi": [
        None,
        50.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        92.349726776,
        85.3203883495,
        78.8564013363,
        72.9079080946,
        67.4300802585,
        62.3825218634,
        57.7287557211,
        53.4357797041,
        49.4736819905,
        45.8153062499,
        42.435959294,
        39.3131549794,
        36.4263891686,
        33.7569413992,
    ],
    "atr": [
        None,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
    ],
}

_REF_TOLERANCE = 1e-6


def verify_indicator_external() -> dict[str, float]:
    """Validate incremental engine against hardcoded reference data."""
    n = len(_REF_INPUT["close"])
    dt = date(2026, 1, 1)

    bars = [
        Bar(
            symbol="REF",
            date=dt,
            open=_REF_INPUT["close"][i],
            high=_REF_INPUT["high"][i],
            low=_REF_INPUT["low"][i],
            close=_REF_INPUT["close"][i],
            volume=1_000_000.0,
        )
        for i in range(n)
    ]

    inc_series = _build_incremental_series(bars)

    diffs: dict[str, float] = {}
    for key, expected in _REF_EXPECTED.items():
        inc_arr = inc_series.get(key)
        if inc_arr is None or len(inc_arr) != n:
            diffs[key] = float("inf")
            continue
        max_diff = 0.0
        for i in range(n):
            exp = expected[i]
            obs = inc_arr[i]
            if exp is None:
                if not np.isnan(obs):
                    max_diff = max(max_diff, abs(obs))
                continue
            if np.isnan(obs):
                max_diff = float("inf")
                continue
            max_diff = max(max_diff, abs(obs - exp))
        diffs[key] = max_diff

    return diffs


def verify_indicator_integrity(bars: list[Bar]) -> dict[str, float]:
    ref_diffs = verify_indicator_external()
    worst = max(ref_diffs.values()) if ref_diffs else 0.0
    if worst > _REF_TOLERANCE:
        ref_diffs["_ref_max"] = worst
        return ref_diffs

    if len(bars) < 250:
        return {}

    close = np.array([b.close for b in bars], dtype=np.float64)
    high = np.array([b.high for b in bars], dtype=np.float64)
    low = np.array([b.low for b in bars], dtype=np.float64)

    bfs: dict[str, np.ndarray] = {}
    for key, period in _VERIFY_KEYS:
        if period is not None:
            bfs[key] = _bruteforce_ema(close, period)
    bfs["rsi"] = _bruteforce_rsi(close)
    bfs["atr"] = _bruteforce_atr(high, low, close)

    macd_line = _bruteforce_ema(close, 12) - _bruteforce_ema(close, 26)
    bfs["macd_line"] = macd_line
    bfs["macd_signal"] = _bruteforce_ema(macd_line, 9)
    bfs["macd_histogram"] = macd_line - bfs["macd_signal"]

    inc = _build_incremental_series(bars)

    start = 249
    diffs: dict[str, float] = {}
    for key in bfs:
        bfs_arr = bfs[key]
        inc_arr = inc.get(key)
        if inc_arr is None or len(inc_arr) != len(bfs_arr):
            continue
        valid = ~np.isnan(bfs_arr[start:]) & ~np.isnan(inc_arr[start:])
        if not np.any(valid):
            continue
        max_diff = float(np.max(np.abs(bfs_arr[start:][valid] - inc_arr[start:][valid])))
        diffs[key] = max_diff

    return diffs

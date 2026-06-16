from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from alpha_quant.domain.derive import (
    _empty_state,
    _REF_INPUT,
    _REF_EXPECTED,
    _REF_TOLERANCE,
    _update_atr,
    _update_ema,
    _update_rsi,
    backfill_indicator_state,
    update_indicator_state,
    verify_indicator_external,
    verify_indicator_integrity,
)
from alpha_quant.domain.models import Bar, IndicatorState


def _bar(
    close: float,
    high: float | None = None,
    low: float | None = None,
    symbol: str = "TEST",
    dt: date | None = None,
) -> Bar:
    return Bar(
        symbol=symbol,
        date=dt or date(2026, 1, 1),
        open=close,
        high=high or (close + 1.0),
        low=low or (close - 1.0),
        close=close,
        volume=1_000_000,
    )


def _state(**values: float) -> IndicatorState:
    init = _empty_state("TEST", date(2026, 1, 1))
    init.update(values)
    return IndicatorState(symbol="TEST", date=date(2026, 1, 1), values=init)


class TestUpdateEma:
    def test_constant_input(self) -> None:
        alpha = 2.0 / (12.0 + 1.0)
        result = _update_ema(np.nan, 10.0, alpha)
        assert result == 10.0
        for _ in range(50):
            result = _update_ema(result, 10.0, alpha)
        assert result == pytest.approx(10.0, abs=1e-10)

    def test_step_change_convergence(self) -> None:
        alpha = 2.0 / (12.0 + 1.0)
        result = _update_ema(np.nan, 10.0, alpha)
        assert result == 10.0
        result = _update_ema(result, 100.0, alpha)
        expected_first = 100.0 * alpha + 10.0 * (1.0 - alpha)
        assert result == pytest.approx(expected_first, abs=1e-10)
        for _ in range(100):
            result = _update_ema(result, 100.0, alpha)
        assert result == pytest.approx(100.0, abs=5e-6)


class TestUpdateRsi:
    def test_up_day(self) -> None:
        gain, loss, rsi = _update_rsi(np.nan, np.nan, 11.0, 10.0)
        assert gain == 1.0
        assert loss == 0.0
        assert rsi == 50.0

    def test_down_day(self) -> None:
        gain, loss, rsi = _update_rsi(np.nan, np.nan, 9.0, 10.0)
        assert gain == 0.0
        assert loss == 1.0
        assert rsi == 50.0

    def test_all_gains_returns_100(self) -> None:
        gain, loss, _ = _update_rsi(0.0, 0.0, 11.0, 10.0)
        assert gain > 0.0
        assert loss == 0.0
        _, _, rsi = _update_rsi(gain, loss, 12.0, 11.0)
        assert rsi == 100.0

    def test_all_losses_approaches_0(self) -> None:
        gain, loss, _ = _update_rsi(0.0, 0.0, 9.0, 10.0)
        assert gain == 0.0
        _, _, rsi = _update_rsi(gain, loss, 8.0, 9.0)
        assert rsi < 1.0


class TestUpdateAtr:
    def test_normal(self) -> None:
        result = _update_atr(np.nan, 12.0, 10.0, 11.0)
        hl = 12.0 - 10.0
        assert result == hl

    def test_gap_up(self) -> None:
        result = _update_atr(np.nan, 15.0, 11.0, 10.0)
        hc = abs(15.0 - 10.0)
        lc = abs(11.0 - 10.0)
        tr = max(15.0 - 11.0, hc, lc)
        assert result == tr


class TestEmptyState:
    def test_creates_all_fields(self) -> None:
        st = _empty_state("TEST", date(2026, 1, 1))
        expected_keys = {
            "ema12", "ema20", "ema26", "ema50", "ema200",
            "macd_line", "macd_signal", "macd_histogram",
            "rsi_avg_gain", "rsi_avg_loss", "rsi",
            "atr", "processed_close", "bar_count",
        }
        assert set(st.keys()) == expected_keys
        for k in expected_keys - {"bar_count"}:
            assert np.isnan(st[k])
        assert st["bar_count"] == 0.0


class TestUpdateIndicatorState:
    def test_single_bar(self) -> None:
        initial = _state()
        bar = _bar(close=100.0)
        result = update_indicator_state(initial, bar)
        assert result.symbol == "TEST"
        assert result.date == bar.date
        assert result.values["ema12"] == 100.0
        assert result.values["ema20"] == 100.0
        assert result.values["bar_count"] == 1.0
        assert result.values["processed_close"] == 100.0
        assert np.isnan(result.values["rsi"])

    def test_two_bars_trend_up(self) -> None:
        initial = _state()
        b1 = _bar(close=100.0, dt=date(2026, 1, 1))
        s1 = update_indicator_state(initial, b1)
        b2 = _bar(close=110.0, dt=date(2026, 1, 2))
        s2 = update_indicator_state(s1, b2)
        assert s2.values["ema12"] > s1.values["ema12"]
        assert s2.values["bar_count"] == 2.0

    def test_two_bars_trend_down(self) -> None:
        initial = _state()
        b1 = _bar(close=110.0, dt=date(2026, 1, 1))
        s1 = update_indicator_state(initial, b1)
        b2 = _bar(close=100.0, dt=date(2026, 1, 2))
        s2 = update_indicator_state(s1, b2)
        assert s2.values["ema12"] < s1.values["ema12"]

    def test_macd_relationship(self) -> None:
        initial = _state()
        dt = date(2026, 1, 1)
        s = update_indicator_state(initial, _bar(close=100.0, dt=dt))
        s = update_indicator_state(s, _bar(close=110.0, dt=dt))
        v = s.values
        assert v["macd_histogram"] == pytest.approx(v["macd_line"] - v["macd_signal"], abs=1e-10)

    def test_bar_count_increments(self) -> None:
        initial = _state()
        dt = date(2026, 1, 1)
        s = update_indicator_state(initial, _bar(close=10.0, dt=dt))
        assert s.values["bar_count"] == 1.0
        s = update_indicator_state(s, _bar(close=11.0, dt=dt))
        assert s.values["bar_count"] == 2.0
        s = update_indicator_state(s, _bar(close=12.0, dt=dt))
        assert s.values["bar_count"] == 3.0

    def test_processed_close_matches_input(self) -> None:
        initial = _state()
        dt = date(2026, 1, 1)
        s = update_indicator_state(initial, _bar(close=42.5, dt=dt))
        assert s.values["processed_close"] == 42.5


class TestBackfillIndicatorState:
    def test_empty_list_raises(self) -> None:
        with pytest.raises(ValueError, match="backfill requires at least one bar"):
            backfill_indicator_state([])

    def test_single_bar(self) -> None:
        bar = _bar(close=100.0, symbol="TEST", dt=date(2026, 1, 1))
        result = backfill_indicator_state([bar])
        assert result.symbol == "TEST"
        assert result.values["ema12"] == 100.0
        assert result.values["bar_count"] == 1.0
        assert result.values["processed_close"] == 100.0

    def test_30_bars_matches_ref_expectations(self) -> None:
        n = len(_REF_INPUT["close"])
        bars = [
            Bar(
                symbol="REF",
                date=date(2026, 1, 1),
                open=_REF_INPUT["close"][i],
                high=_REF_INPUT["high"][i],
                low=_REF_INPUT["low"][i],
                close=_REF_INPUT["close"][i],
                volume=1_000_000,
            )
            for i in range(n)
        ]
        result = backfill_indicator_state(bars)
        for i in range(n):
            label = f"bar[{i}] close={_REF_INPUT['close'][i]}"
            exp_ema = _REF_EXPECTED["ema20"][i]
            obs_ema = result.values["ema20"] if i == n - 1 else np.nan
        ema_series = _build_ema_series(bars)
        for i in range(n):
            exp_ema = _REF_EXPECTED["ema20"][i]
            obs_ema = ema_series[i]
            if exp_ema is None:
                assert obs_ema is None, f"bar[{i}] ema20 expected None"
            else:
                assert obs_ema == pytest.approx(exp_ema, abs=_REF_TOLERANCE), f"bar[{i}] ema20 mismatch"

    def test_backfill_30_bars_rsi(self) -> None:
        n = len(_REF_INPUT["close"])
        bars = [
            Bar(
                symbol="REF",
                date=date(2026, 1, 1),
                open=_REF_INPUT["close"][i],
                high=_REF_INPUT["high"][i],
                low=_REF_INPUT["low"][i],
                close=_REF_INPUT["close"][i],
                volume=1_000_000,
            )
            for i in range(n)
        ]
        rsi_series = _build_rsi_series(bars)
        for i in range(n):
            exp = _REF_EXPECTED["rsi"][i]
            obs = rsi_series[i]
            if exp is None:
                assert obs is None, f"bar[{i}] rsi expected None"
            else:
                assert obs == pytest.approx(exp, abs=_REF_TOLERANCE), f"bar[{i}] rsi mismatch"

    def test_backfill_30_bars_atr(self) -> None:
        n = len(_REF_INPUT["close"])
        bars = [
            Bar(
                symbol="REF",
                date=date(2026, 1, 1),
                open=_REF_INPUT["close"][i],
                high=_REF_INPUT["high"][i],
                low=_REF_INPUT["low"][i],
                close=_REF_INPUT["close"][i],
                volume=1_000_000,
            )
            for i in range(n)
        ]
        atr_series = _build_atr_series(bars)
        for i in range(n):
            exp = _REF_EXPECTED["atr"][i]
            obs = atr_series[i]
            if exp is None:
                assert obs is None, f"bar[{i}] atr expected None"
            else:
                assert obs == pytest.approx(exp, abs=_REF_TOLERANCE), f"bar[{i}] atr mismatch"


class TestVerifyExternal:
    def test_against_ref_expected(self) -> None:
        diffs = verify_indicator_external()
        assert isinstance(diffs, dict)
        for key, diff in diffs.items():
            assert diff < _REF_TOLERANCE, f"{key} max diff {diff} >= {_REF_TOLERANCE}"


class TestVerifyIntegrity:
    def test_fewer_than_250_bars_returns_empty(self) -> None:
        bars = [_bar(close=100.0, dt=date(2026, 1, 1)) for _ in range(100)]
        result = verify_indicator_integrity(bars)
        assert result == {}

    def test_300_bars_returns_diffs(self) -> None:
        dt = date(2026, 1, 1)
        bars = [
            Bar(
                symbol="TEST",
                date=dt,
                open=float(i),
                high=float(i) + 1.0,
                low=float(i),
                close=float(i) + 0.5,
                volume=1_000_000,
            )
            for i in range(300)
        ]
        result = verify_indicator_integrity(bars)
        assert isinstance(result, dict)
        assert len(result) > 0
        for diff in result.values():
            assert diff < 1e-8


def _build_ema_series(bars: list[Bar]) -> list[float | None]:
    from alpha_quant.domain.derive import _build_incremental_series
    series = _build_incremental_series(bars)
    return [float(v) if not np.isnan(v) else None for v in series["ema20"]]


def _build_rsi_series(bars: list[Bar]) -> list[float | None]:
    from alpha_quant.domain.derive import _build_incremental_series
    series = _build_incremental_series(bars)
    return [float(v) if not np.isnan(v) else None for v in series["rsi"]]


def _build_atr_series(bars: list[Bar]) -> list[float | None]:
    from alpha_quant.domain.derive import _build_incremental_series
    series = _build_incremental_series(bars)
    return [float(v) if not np.isnan(v) else None for v in series["atr"]]

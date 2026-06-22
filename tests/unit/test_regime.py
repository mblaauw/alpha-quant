"""Unit tests for M2 regime detection (domain.regime)."""

from datetime import date

import pytest

from domain.models import IndicatorState
from domain.regime import REGIME_MULTIPLIERS, detect


def _state(close: float, ema50: float, ema200: float, bar_count: float = 300.0) -> IndicatorState:
    return IndicatorState(
        symbol="SPY",
        date=date(2026, 6, 11),
        values={
            "processed_close": close,
            "ema50": ema50,
            "ema200": ema200,
            "bar_count": bar_count,
        },
    )


class TestDetect:
    def test_risk_on(self) -> None:
        state = _state(close=210, ema50=200, ema200=190)
        result = detect(state, vix_level=15.0, breadth=0.6)
        assert result == "RISK_ON"
        assert REGIME_MULTIPLIERS[result] == 1.0

    def test_caution_when_missing_indicators(self) -> None:
        state = IndicatorState(
            symbol="SPY",
            date=date(2026, 6, 11),
            values={},
        )
        result = detect(state, vix_level=15.0, breadth=0.5)
        assert result == "CAUTION"

    @pytest.mark.parametrize(
        "close,ema50,ema200,vix,breadth,expected",
        [
            (190, 200, 180, 15.0, 0.5, "CAUTION"),
            (210, 190, 200, 15.0, 0.5, "CAUTION"),
            (210, 200, 190, 22.0, 0.5, "CAUTION"),
            (210, 200, 190, 15.0, 0.3, "CAUTION"),
            (210, 200, 190, 20.0, 0.5, "CAUTION"),
            (210, 200, 190, 15.0, 0.4, "CAUTION"),
        ],
    )
    def test_caution_scenarios(self, close, ema50, ema200, vix, breadth, expected):
        state = _state(close=close, ema50=ema50, ema200=ema200)
        result = detect(state, vix_level=vix, breadth=breadth)
        assert result == expected

    @pytest.mark.parametrize(
        "close,ema50,ema200,vix,breadth,expected",
        [
            (170, 190, 180, 15.0, 0.5, "RISK_OFF"),
            (180, 190, 170, 35.0, 0.3, "RISK_OFF"),
        ],
    )
    def test_risk_off_scenarios(self, close, ema50, ema200, vix, breadth, expected):
        state = _state(close=close, ema50=ema50, ema200=ema200)
        result = detect(state, vix_level=vix, breadth=breadth)
        assert result == expected
        if expected == "RISK_OFF":
            assert REGIME_MULTIPLIERS[result] == 0.0

    def test_none_vix_with_good_indicators(self) -> None:
        state = _state(close=210, ema50=200, ema200=190)
        result = detect(state, vix_level=None, breadth=0.6)
        assert result == "RISK_ON"

    def test_extreme_breadth_triggers_caution(self) -> None:
        state = _state(close=210, ema50=200, ema200=190)
        result = detect(state, vix_level=15.0, breadth=0.15)
        assert result == "CAUTION"

    def test_none_breadth_with_good_indicators(self) -> None:
        state = _state(close=210, ema50=200, ema200=190)
        result = detect(state, vix_level=15.0, breadth=None)
        assert result == "RISK_ON"

    def test_bearish_with_very_low_breadth_triggers_risk_off(self) -> None:
        bear_state = _state(close=170, ema50=190, ema200=180)
        result = detect(bear_state, vix_level=15.0, breadth=0.15)
        assert result == "RISK_OFF"

    def test_bearish_ema50_cross_with_very_low_breadth_stays_caution(self) -> None:
        result = detect(_state(close=210, ema50=190, ema200=200), vix_level=15.0, breadth=0.1)
        assert result == "CAUTION"

    # --- Warmup tests ---

    def test_no_warmup_returns_caution(self) -> None:
        """With bar_count=0, all EMA200-dependent paths return CAUTION."""
        state = _state(close=170, ema50=190, ema200=180, bar_count=0.0)
        result = detect(state, vix_level=15.0, breadth=0.5)
        assert result == "CAUTION"

    def test_just_under_warmup_still_cautions(self) -> None:
        """With bar_count=199 (just under 200), EMA200-dependent paths still
        return CAUTION instead of RISK_OFF."""
        state = _state(close=170, ema50=190, ema200=180, bar_count=199.0)
        result = detect(state, vix_level=15.0, breadth=0.5)
        assert result == "CAUTION"

    def test_just_under_warmup_risk_on_path(self) -> None:
        """With bar_count=199, the non-EMA200 path to RISK_ON still works."""
        state = _state(close=210, ema50=200, ema200=190, bar_count=199.0)
        result = detect(state, vix_level=15.0, breadth=0.6)
        assert result == "RISK_ON"

    def test_fully_warmed_produces_risk_off(self) -> None:
        """With bar_count=200+, the RISK_OFF path is unblocked."""
        state = _state(close=170, ema50=190, ema200=180, bar_count=200.0)
        result = detect(state, vix_level=15.0, breadth=0.5)
        assert result == "RISK_OFF"

    def test_warmup_with_high_vix(self) -> None:
        """With bar_count=199 and vix>=20, returns CAUTION (not RISK_OFF)."""
        state = _state(close=210, ema50=200, ema200=190, bar_count=199.0)
        result = detect(state, vix_level=22.0, breadth=0.5)
        assert result == "CAUTION"

    def test_warmup_with_extreme_breadth(self) -> None:
        """With bar_count=199 and breadth<=0.2, returns CAUTION (breadth check
        before _check_risk_off)."""
        state = _state(close=210, ema50=200, ema200=190, bar_count=199.0)
        result = detect(state, vix_level=15.0, breadth=0.15)
        assert result == "CAUTION"

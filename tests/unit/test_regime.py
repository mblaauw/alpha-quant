"""Unit tests for M2 regime detection (alpha_quant.domain.regime)."""

from datetime import date

from alpha_quant.domain.models import IndicatorState
from alpha_quant.domain.regime import REGIME_MULTIPLIERS, detect


def _state(close: float, ema50: float, ema200: float) -> IndicatorState:
    return IndicatorState(
        symbol="SPY",
        date=date(2026, 6, 11),
        values={"prev_close": close, "ema50": ema50, "ema200": ema200},
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

    def test_caution_when_close_below_ema50(self) -> None:
        state = _state(close=190, ema50=200, ema200=180)
        result = detect(state, vix_level=15.0, breadth=0.5)
        assert result == "CAUTION"

    def test_caution_when_ema50_below_ema200(self) -> None:
        state = _state(close=210, ema50=190, ema200=200)
        result = detect(state, vix_level=15.0, breadth=0.5)
        assert result == "CAUTION"

    def test_caution_when_vix_above_20(self) -> None:
        state = _state(close=210, ema50=200, ema200=190)
        result = detect(state, vix_level=22.0, breadth=0.5)
        assert result == "CAUTION"

    def test_caution_when_breadth_below_04(self) -> None:
        state = _state(close=210, ema50=200, ema200=190)
        result = detect(state, vix_level=15.0, breadth=0.3)
        assert result == "CAUTION"

    def test_risk_off_when_close_below_ema200(self) -> None:
        state = _state(close=170, ema50=190, ema200=180)
        result = detect(state, vix_level=15.0, breadth=0.5)
        assert result == "RISK_OFF"
        assert REGIME_MULTIPLIERS[result] == 0.0

    def test_risk_off_when_vix_above_30(self) -> None:
        state = _state(close=180, ema50=190, ema200=170)
        result = detect(state, vix_level=35.0, breadth=0.3)
        assert result == "RISK_OFF"

    def test_caution_at_vix_exactly_20(self) -> None:
        state = _state(close=210, ema50=200, ema200=190)
        result = detect(state, vix_level=20.0, breadth=0.5)
        assert result == "CAUTION"

    def test_caution_at_breadth_exactly_04(self) -> None:
        state = _state(close=210, ema50=200, ema200=190)
        result = detect(state, vix_level=15.0, breadth=0.4)
        assert result == "CAUTION"

    def test_none_vix_with_good_indicators(self) -> None:
        state = _state(close=210, ema50=200, ema200=190)
        result = detect(state, vix_level=None, breadth=0.6)
        assert result == "RISK_ON"

    def test_none_breadth_with_good_indicators(self) -> None:
        state = _state(close=210, ema50=200, ema200=190)
        result = detect(state, vix_level=15.0, breadth=None)
        assert result == "RISK_ON"

    def test_bearish_with_very_low_breadth_stays_caution(self) -> None:
        result = detect(_state(close=170, ema50=190, ema200=180), vix_level=15.0, breadth=0.15)
        assert result == "CAUTION"

    def test_bearish_ema50_cross_with_very_low_breadth_stays_caution(self) -> None:
        result = detect(_state(close=210, ema50=190, ema200=200), vix_level=15.0, breadth=0.1)
        assert result == "CAUTION"

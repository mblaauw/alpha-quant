"""Unit tests for source degradation fallback (alpha_quant.domain.degradation)."""

from alpha_quant.domain.degradation import (
    DegradationStatus,
    blackout_window_days,
    m3_threshold_multiplier,
)


class TestDegradationStatus:
    def test_default_all_false(self) -> None:
        d = DegradationStatus()
        assert d.insider_degraded is False
        assert d.crowding_degraded is False
        assert d.fundamentals_degraded is False
        assert d.earnings_stale is False
        assert d.sec_degraded is False

    def test_set_flags(self) -> None:
        d = DegradationStatus(insider_degraded=True, crowding_degraded=True)
        assert d.insider_degraded is True
        assert d.crowding_degraded is True
        assert d.fundamentals_degraded is False


class TestM3ThresholdMultiplier:
    def test_normal_returns_1_0(self) -> None:
        assert m3_threshold_multiplier(DegradationStatus()) == 1.0

    def test_crowding_degraded_returns_1_2(self) -> None:
        d = DegradationStatus(crowding_degraded=True)
        assert m3_threshold_multiplier(d) == 1.2

    def test_other_degradations_dont_affect(self) -> None:
        d = DegradationStatus(
            insider_degraded=True,
            fundamentals_degraded=True,
            earnings_stale=True,
        )
        assert m3_threshold_multiplier(d) == 1.0


class TestBlackoutWindowDays:
    def test_normal_returns_3(self) -> None:
        assert blackout_window_days(DegradationStatus()) == 3

    def test_earnings_stale_returns_4(self) -> None:
        d = DegradationStatus(earnings_stale=True)
        assert blackout_window_days(d) == 4

    def test_other_degradations_dont_affect(self) -> None:
        d = DegradationStatus(
            insider_degraded=True,
            crowding_degraded=True,
            fundamentals_degraded=True,
        )
        assert blackout_window_days(d) == 3

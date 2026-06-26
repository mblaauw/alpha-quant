"""Unit tests for source degradation fallback (domain.degradation)."""

from datetime import UTC, datetime, timedelta

import pytest

from alpha_quant.domain.degradation import (
    DegradationStatus,
    blackout_window_days,
    health_to_degradation,
    is_price_stale,
    m3_threshold_multiplier,
)


class TestDegradationStatus:
    def test_default_all_false(self) -> None:
        d = DegradationStatus()
        assert d.insider_degraded is False
        assert d.crowding_degraded is False
        assert d.fundamentals_degraded is False
        assert d.earnings_stale is False

    def test_set_flags(self) -> None:
        d = DegradationStatus(insider_degraded=True, crowding_degraded=True)
        assert d.insider_degraded is True
        assert d.crowding_degraded is True
        assert d.fundamentals_degraded is False


class TestM3ThresholdMultiplier:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (DegradationStatus(), 1.0),
            (DegradationStatus(crowding_degraded=True), 1.2),
            (
                DegradationStatus(
                    insider_degraded=True, fundamentals_degraded=True, earnings_stale=True
                ),
                1.0,
            ),
        ],
    )
    def test_multiplier(self, status: DegradationStatus, expected: float) -> None:
        assert m3_threshold_multiplier(status) == expected


class TestBlackoutWindowDays:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (DegradationStatus(), 3),
            (DegradationStatus(earnings_stale=True), 4),
            (
                DegradationStatus(
                    insider_degraded=True, crowding_degraded=True, fundamentals_degraded=True
                ),
                3,
            ),
        ],
    )
    def test_window_days(self, status: DegradationStatus, expected: int) -> None:
        assert blackout_window_days(status) == expected


class TestHealthToDegradation:
    @pytest.mark.parametrize(
        ("health", "expected_fundamentals", "expected_insider", "expected_crowding"),
        [
            (
                {
                    "datasets": {
                        "bars": {"status": "ok", "row_count": 100},
                        "fundamentals": {"status": "ok", "row_count": 10},
                        "insider_tx": {"status": "ok", "row_count": 5},
                        "attention": {"status": "ok", "row_count": 20},
                    }
                },
                False,
                False,
                False,
            ),
            (
                {"datasets": {"insider_tx": {"row_count": 5}, "attention": {"row_count": 20}}},
                True,
                False,
                False,
            ),
            (
                {"datasets": {"fundamentals": {"row_count": 10}, "attention": {"row_count": 20}}},
                False,
                True,
                False,
            ),
            (
                {"datasets": {"fundamentals": {"row_count": 10}, "insider_tx": {"row_count": 5}}},
                False,
                False,
                True,
            ),
            ({}, True, True, True),
        ],
    )
    def test_degradation(
        self,
        health: dict,
        expected_fundamentals: bool,
        expected_insider: bool,
        expected_crowding: bool,
    ) -> None:
        d = health_to_degradation(health)
        assert d.fundamentals_degraded is expected_fundamentals
        assert d.insider_degraded is expected_insider
        assert d.crowding_degraded is expected_crowding


class TestIsPriceStale:
    @pytest.mark.parametrize(
        ("health", "staleness_hours", "expected"),
        [
            (
                {
                    "datasets": {
                        "bars": {
                            "latest_available_at": (
                                datetime(2026, 6, 15, 12, tzinfo=UTC) - timedelta(hours=12)
                            ).isoformat()
                        }
                    }
                },
                30,
                False,
            ),
            (
                {
                    "datasets": {
                        "bars": {
                            "latest_available_at": (
                                datetime(2026, 6, 15, 12, tzinfo=UTC) - timedelta(hours=48)
                            ).isoformat()
                        }
                    }
                },
                30,
                True,
            ),
            ({}, 30, True),
            ({"datasets": {"bars": {"row_count": 0}}}, 30, True),
        ],
    )
    def test_stale(self, health: dict, staleness_hours: int, expected: bool) -> None:
        now = datetime(2026, 6, 15, 12, tzinfo=UTC)
        assert is_price_stale(health, staleness_hours=staleness_hours, now=now) is expected

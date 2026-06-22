"""Unit tests for source degradation fallback (domain.degradation)."""

from datetime import UTC, datetime, timedelta

from domain.degradation import (
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


class TestHealthToDegradation:
    def test_all_datasets_healthy(self) -> None:
        health = {
            "datasets": {
                "bars": {"status": "ok", "row_count": 100},
                "fundamentals": {"status": "ok", "row_count": 10},
                "insider_tx": {"status": "ok", "row_count": 5},
                "attention": {"status": "ok", "row_count": 20},
            }
        }
        d = health_to_degradation(health)
        assert d.fundamentals_degraded is False
        assert d.insider_degraded is False
        assert d.crowding_degraded is False

    def test_missing_fundamentals_sets_flag(self) -> None:
        health = {"datasets": {"insider_tx": {"row_count": 5}, "attention": {"row_count": 20}}}
        d = health_to_degradation(health)
        assert d.fundamentals_degraded is True

    def test_missing_insider_sets_flag(self) -> None:
        health = {"datasets": {"fundamentals": {"row_count": 10}, "attention": {"row_count": 20}}}
        d = health_to_degradation(health)
        assert d.insider_degraded is True

    def test_missing_attention_sets_crowding_flag(self) -> None:
        health = {"datasets": {"fundamentals": {"row_count": 10}, "insider_tx": {"row_count": 5}}}
        d = health_to_degradation(health)
        assert d.crowding_degraded is True

    def test_empty_health(self) -> None:
        d = health_to_degradation({})
        assert d.fundamentals_degraded is True
        assert d.insider_degraded is True
        assert d.crowding_degraded is True


class TestIsPriceStale:
    def test_fresh_bars_not_stale(self) -> None:
        now = datetime(2026, 6, 15, 12, tzinfo=UTC)
        health = {
            "datasets": {
                "bars": {"latest_available_at": (now - timedelta(hours=12)).isoformat()},
            }
        }
        assert is_price_stale(health, staleness_hours=30, now=now) is False

    def test_stale_bars_triggers_halt(self) -> None:
        now = datetime(2026, 6, 15, 12, tzinfo=UTC)
        health = {
            "datasets": {
                "bars": {"latest_available_at": (now - timedelta(hours=48)).isoformat()},
            }
        }
        assert is_price_stale(health, staleness_hours=30, now=now) is True

    def test_no_bars_dataset_is_stale(self) -> None:
        assert is_price_stale({}) is True

    def test_no_latest_available_at_is_stale(self) -> None:
        health = {"datasets": {"bars": {"row_count": 0}}}
        assert is_price_stale(health) is True

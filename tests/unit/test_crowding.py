"""Unit tests for M6 crowding veto (domain.crowding)."""

from datetime import date, timedelta

from domain.crowding import CrowdingVerdict, evaluate


class TestEvaluate:
    def test_no_z_score_no_block(self) -> None:
        result = evaluate(z_score=None, blocked_until=None, as_of_date=date(2026, 6, 11))
        assert result.blocked is False

    def test_low_z_score_no_block(self) -> None:
        result = evaluate(z_score=1.5, blocked_until=None, as_of_date=date(2026, 6, 11))
        assert result.blocked is False

    def test_z_score_exactly_3_no_block(self) -> None:
        result = evaluate(z_score=3.0, blocked_until=None, as_of_date=date(2026, 6, 11))
        assert result.blocked is False

    def test_z_score_above_3_triggers_block(self) -> None:
        result = evaluate(z_score=4.2, blocked_until=None, as_of_date=date(2026, 6, 11))
        assert result.blocked is True
        assert result.blocked_until is not None
        assert "z-score" in (result.reason or "")

    def test_block_14_days_forward(self) -> None:
        as_of = date(2026, 6, 11)
        result = evaluate(z_score=5.0, blocked_until=None, as_of_date=as_of)
        assert result.blocked_until == as_of + timedelta(days=14)

    def test_active_block_continues(self) -> None:
        blocked_until = date(2026, 6, 20)
        result = evaluate(z_score=1.0, blocked_until=blocked_until, as_of_date=date(2026, 6, 15))
        assert result.blocked is True
        assert result.blocked_until == blocked_until

    def test_expired_block_lifted(self) -> None:
        result = evaluate(
            z_score=1.0,
            blocked_until=date(2026, 6, 10),
            as_of_date=date(2026, 6, 11),
        )
        assert result.blocked is False

    def test_active_block_extended_by_new_high_z_score(self) -> None:
        blocked_until = date(2026, 6, 20)
        result = evaluate(z_score=8.0, blocked_until=blocked_until, as_of_date=date(2026, 6, 18))
        assert result.blocked is True
        assert result.blocked_until > blocked_until

    def test_active_block_with_new_z_score_extends(self) -> None:
        blocked_until = date(2026, 6, 20)
        result = evaluate(z_score=6.0, blocked_until=blocked_until, as_of_date=date(2026, 6, 15))
        assert result.blocked is True
        assert result.blocked_until >= blocked_until

    def test_block_reason_includes_date(self) -> None:
        result = evaluate(z_score=4.0, blocked_until=None, as_of_date=date(2026, 6, 11))
        assert result.reason is not None
        assert "2026-06-25" in result.reason

    def test_active_block_reason_includes_date(self) -> None:
        blocked_until = date(2026, 6, 20)
        result = evaluate(z_score=4.0, blocked_until=blocked_until, as_of_date=date(2026, 6, 15))
        assert result.reason is not None
        assert "extended" in result.reason

    def test_degraded_source_lifts_block(self) -> None:
        blocked_until = date(2026, 6, 10)
        result = evaluate(z_score=None, blocked_until=blocked_until, as_of_date=date(2026, 6, 11))
        assert result.blocked is False

    def test_crowding_verdict_defaults(self) -> None:
        v = CrowdingVerdict(blocked=False)
        assert v.blocked_until is None
        assert v.reason is None

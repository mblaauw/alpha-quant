"""Unit tests for self-consistency invariants (alpha_quant.domain.invariants)."""

from alpha_quant.domain.invariants import InvariantViolation, check_invariants
from alpha_quant.domain.models import Position


def _position(
    symbol: str = "AAPL",
    quantity: float = 100.0,
    avg_cost: float = 100.0,
    stop_price: float | None = 90.0,
    market_value: float | None = 10_000.0,
) -> Position:
    return Position(
        symbol=symbol,
        quantity=quantity,
        entry_price=avg_cost,
        avg_cost=avg_cost,
        current_price=avg_cost,
        stop_price=stop_price,
        market_value=market_value,
    )


class TestCheckInvariants:
    def test_i1_passes_when_consistent(self) -> None:
        pos = _position(market_value=6_000.0)
        violations = check_invariants(
            equity=10_000.0,
            cash=4_000.0,
            positions=[pos],
        )
        i1s = [v for v in violations if v.check == "I1_cash_plus_mark_equals_equity"]
        assert len(i1s) == 0

    def test_i1_fails_when_inconsistent(self) -> None:
        pos = _position(market_value=5_000.0)
        violations = check_invariants(
            equity=10_000.0,
            cash=4_000.0,
            positions=[pos],
        )
        i1s = [v for v in violations if v.check == "I1_cash_plus_mark_equals_equity"]
        assert len(i1s) == 1

    def test_i5_passes_when_risk_within_tolerance(self) -> None:
        pos = _position(avg_cost=100.0, stop_price=99.0, market_value=10_000.0)
        violations = check_invariants(
            equity=100_000.0,
            cash=90_000.0,
            positions=[pos],
            risk_tolerance_pct=0.02,
        )
        i5s = [v for v in violations if v.check == "I5_risk_at_stop"]
        assert len(i5s) == 0

    def test_i5_fails_when_risk_exceeds_tolerance(self) -> None:
        pos = _position(avg_cost=100.0, stop_price=50.0, market_value=10_000.0)
        violations = check_invariants(
            equity=100_000.0,
            cash=90_000.0,
            positions=[pos],
            risk_tolerance_pct=0.02,
        )
        i5s = [v for v in violations if v.check == "I5_risk_at_stop"]
        assert len(i5s) == 1

    def test_i5_skipped_when_no_stop_price(self) -> None:
        pos = _position(stop_price=None, market_value=10_000.0, avg_cost=100.0)
        violations = check_invariants(
            equity=100_000.0,
            cash=90_000.0,
            positions=[pos],
        )
        i5s = [v for v in violations if v.check == "I5_risk_at_stop"]
        assert len(i5s) == 0

    def test_i5_skipped_when_stop_above_cost(self) -> None:
        pos = _position(avg_cost=100.0, stop_price=110.0, market_value=10_000.0)
        violations = check_invariants(
            equity=100_000.0,
            cash=90_000.0,
            positions=[pos],
        )
        i5s = [v for v in violations if v.check == "I5_risk_at_stop"]
        assert len(i5s) == 0

    def test_i6_passes_when_exposure_within_bounds(self) -> None:
        pos = _position(market_value=40_000.0)
        violations = check_invariants(
            equity=100_000.0,
            cash=60_000.0,
            positions=[pos],
            max_gross_exposure=0.80,
        )
        i6s = [v for v in violations if v.check == "I6_gross_exposure"]
        assert len(i6s) == 0

    def test_i6_fails_when_exposure_exceeds(self) -> None:
        pos = _position(market_value=90_000.0)
        violations = check_invariants(
            equity=100_000.0,
            cash=10_000.0,
            positions=[pos],
            max_gross_exposure=0.80,
        )
        i6s = [v for v in violations if v.check == "I6_gross_exposure"]
        assert len(i6s) == 1

    def test_i6_skipped_when_equity_zero(self) -> None:
        pos = _position(market_value=90_000.0)
        violations = check_invariants(
            equity=0.0,
            cash=0.0,
            positions=[pos],
        )
        i6s = [v for v in violations if v.check == "I6_gross_exposure"]
        assert len(i6s) == 0

    def test_multiple_violations_returned(self) -> None:
        pos = _position(market_value=90_000.0, avg_cost=100.0, stop_price=50.0)
        violations = check_invariants(
            equity=100_000.0,
            cash=5_000.0,
            positions=[pos],
            max_gross_exposure=0.50,
            risk_tolerance_pct=0.01,
        )
        checks = [v.check for v in violations]
        assert "I1_cash_plus_mark_equals_equity" in checks
        assert "I6_gross_exposure" in checks
        assert "I5_risk_at_stop" in checks


class TestInvariantViolation:
    def test_dataclass_attributes(self) -> None:
        v = InvariantViolation(check="I1_test", detail="something wrong")
        assert v.check == "I1_test"
        assert v.detail == "something wrong"

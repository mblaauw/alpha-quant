"""Unit tests for self-consistency invariants (domain.invariants)."""

import pytest

from alpha_quant.domain.invariants import check_invariants
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


I1_CASH_PLUS_MARK = "I1_cash_plus_mark_equals_equity"
I5_RISK_AT_STOP = "I5_risk_at_stop"
I6_GROSS_EXPOSURE = "I6_gross_exposure"


class TestCheckInvariants:
    @pytest.mark.parametrize(
        ("check_name", "position", "equity", "cash", "extra_kwargs", "expected_count"),
        [
            (I1_CASH_PLUS_MARK, _position(market_value=6_000.0), 10_000.0, 4_000.0, {}, 0),
            (I1_CASH_PLUS_MARK, _position(market_value=5_000.0), 10_000.0, 4_000.0, {}, 1),
            (
                I5_RISK_AT_STOP,
                _position(avg_cost=100.0, stop_price=99.0, market_value=10_000.0),
                100_000.0,
                90_000.0,
                {"risk_tolerance_pct": 0.02},
                0,
            ),
            (
                I5_RISK_AT_STOP,
                _position(avg_cost=100.0, stop_price=50.0, market_value=10_000.0),
                100_000.0,
                90_000.0,
                {"risk_tolerance_pct": 0.02},
                1,
            ),
            (
                I5_RISK_AT_STOP,
                _position(stop_price=None, market_value=10_000.0, avg_cost=100.0),
                100_000.0,
                90_000.0,
                {},
                0,
            ),
            (
                I5_RISK_AT_STOP,
                _position(avg_cost=100.0, stop_price=110.0, market_value=10_000.0),
                100_000.0,
                90_000.0,
                {},
                0,
            ),
            (
                I6_GROSS_EXPOSURE,
                _position(market_value=40_000.0),
                100_000.0,
                60_000.0,
                {"max_gross_exposure": 0.80},
                0,
            ),
            (
                I6_GROSS_EXPOSURE,
                _position(market_value=90_000.0),
                100_000.0,
                10_000.0,
                {"max_gross_exposure": 0.80},
                1,
            ),
            (I6_GROSS_EXPOSURE, _position(market_value=90_000.0), 0.0, 0.0, {}, 0),
        ],
    )
    def test_invariant(
        self,
        check_name: str,
        position: Position,
        equity: float,
        cash: float,
        extra_kwargs: dict,
        expected_count: int,
    ) -> None:
        violations = check_invariants(
            equity=equity, cash=cash, positions=[position], **extra_kwargs
        )
        matched = [v for v in violations if v.check == check_name]
        assert len(matched) == expected_count

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

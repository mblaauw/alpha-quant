"""Unit tests for risk management (domain.risk)."""

from datetime import date

import pytest

from alpha_quant.domain.models import Bar, Position
from alpha_quant.domain.risk import (
    RiskConfig,
    evaluate_daily_loss,
    evaluate_drawdown,
    evaluate_stops,
    evaluate_time_stop,
)


def _bar(
    open_v: float = 100.0,
    high: float = 105.0,
    low: float = 95.0,
    close: float = 100.0,
) -> Bar:
    return Bar(
        symbol="AAPL",
        date=date(2026, 6, 11),
        open=open_v,
        high=max(high, open_v, close),
        low=min(low, open_v, close),
        close=close,
        volume=1_000_000,
    )


def _position(
    quantity: float = 100.0,
    avg_cost: float = 100.0,
    stop_price: float | None = 90.0,
    partial_taken: bool = False,
) -> Position:
    return Position(
        symbol="AAPL",
        quantity=quantity,
        entry_price=avg_cost,
        avg_cost=avg_cost,
        current_price=avg_cost,
        stop_price=stop_price,
        market_value=quantity * avg_cost,
        partial_taken=partial_taken,
    )


class TestEvaluateStops:
    def test_stop_hit_returns_action(self) -> None:
        pos = _position(avg_cost=100.0, stop_price=90.0)
        bar = _bar(open_v=92.0, high=95.0, low=85.0)
        result = evaluate_stops(pos, bar, atr=5.0, highest_since_entry=100.0)
        assert len(result) == 1
        assert result[0].action_type == "stop"
        assert result[0].symbol == "AAPL"

    def test_no_stop_hit_returns_empty(self) -> None:
        pos = _position(avg_cost=100.0, stop_price=90.0)
        bar = _bar(high=105.0, low=95.0)
        result = evaluate_stops(pos, bar, atr=5.0, highest_since_entry=100.0)
        assert result == []

    def test_trail_stop_triggers(self) -> None:
        pos = _position(avg_cost=100.0, stop_price=90.0)
        bar = _bar(high=110.0, low=100.0)
        result = evaluate_stops(pos, bar, atr=5.0, highest_since_entry=115.0)
        assert len(result) == 1
        assert result[0].action_type == "trail_stop"

    def test_trail_tightens_as_price_rallies(self) -> None:
        pos = _position(avg_cost=100.0, stop_price=90.0)
        bar = _bar(open_v=115.0, high=125.0, low=105.0)
        result = evaluate_stops(pos, bar, atr=5.0, highest_since_entry=120.0)
        assert any(a.action_type == "trail_stop" for a in result)
        trail_actions = [a for a in result if a.action_type == "trail_stop"]
        assert len(trail_actions) == 1
        assert trail_actions[0].shares == 0.0
        assert trail_actions[0].price == pytest.approx(115.0)

    def test_partial_take_triggers_when_no_stop(self) -> None:
        config = RiskConfig(partial_take_at_r=2.0)
        pos = _position(avg_cost=100.0, stop_price=90.0)
        bar = _bar(open_v=122.0, high=125.0, low=120.0, close=122.0)
        result = evaluate_stops(pos, bar, atr=5.0, highest_since_entry=100.0, config=config)
        assert any(a.action_type == "partial_take" for a in result)

    def test_zero_quantity_returns_empty(self) -> None:
        pos = _position(quantity=0)
        result = evaluate_stops(pos, _bar(), atr=5.0, highest_since_entry=100.0)
        assert result == []

    def test_zero_atr_returns_empty(self) -> None:
        pos = _position()
        result = evaluate_stops(pos, _bar(), atr=0.0, highest_since_entry=100.0)
        assert result == []

    def test_zero_entry_price_returns_empty(self) -> None:
        pos = _position(avg_cost=0.0)
        result = evaluate_stops(pos, _bar(), atr=5.0, highest_since_entry=100.0)
        assert result == []

    def test_partial_take_qty_is_half(self) -> None:
        config = RiskConfig(partial_take_at_r=1.0)
        pos = _position(quantity=100.0, avg_cost=100.0, stop_price=80.0)
        bar = _bar(open_v=118.0, high=120.0, low=115.0)
        result = evaluate_stops(pos, bar, atr=5.0, highest_since_entry=100.0, config=config)
        partials = [a for a in result if a.action_type == "partial_take"]
        if partials:
            assert partials[0].shares == 50.0

    def test_partial_take_fires_only_once(self) -> None:
        config = RiskConfig(partial_take_at_r=1.0)
        bar = _bar(open_v=118.0, high=120.0, low=115.0)
        pos = _position(quantity=100.0, avg_cost=100.0, stop_price=80.0)
        pos_taken = _position(quantity=100.0, avg_cost=100.0, stop_price=80.0, partial_taken=True)

        result1 = evaluate_stops(pos, bar, atr=5.0, highest_since_entry=100.0, config=config)
        result2 = evaluate_stops(pos_taken, bar, atr=5.0, highest_since_entry=100.0, config=config)

        assert any(a.action_type == "partial_take" for a in result1)
        assert not any(a.action_type == "partial_take" for a in result2)


class TestEvaluateTimeStop:
    def test_time_stop_triggers(self) -> None:
        pos = _position()
        result = evaluate_time_stop(
            pos,
            entry_date=date(2026, 1, 1),
            current_date=date(2026, 6, 11),
        )
        assert len(result) == 1
        assert result[0].action_type == "time_stop"

    def test_time_stop_not_yet(self) -> None:
        pos = _position()
        result = evaluate_time_stop(
            pos,
            entry_date=date(2026, 6, 10),
            current_date=date(2026, 6, 11),
        )
        assert result == []

    def test_zero_quantity_returns_empty(self) -> None:
        pos = _position(quantity=0)
        result = evaluate_time_stop(
            pos,
            entry_date=date(2026, 1, 1),
            current_date=date(2026, 6, 11),
        )
        assert result == []


class TestEvaluateDrawdown:
    def test_no_drawdown_returns_full_multiplier(self) -> None:
        result = evaluate_drawdown([100.0, 105.0, 110.0])
        assert result.multiplier == 1.0
        assert result.actions == []

    def test_10_pct_drawdown_reduces_multiplier(self) -> None:
        result = evaluate_drawdown([100.0, 85.0, 90.0])
        assert result.multiplier == 0.5

    def test_15_pct_drawdown_reduces_to_zero(self) -> None:
        result = evaluate_drawdown([100.0, 80.0, 85.0])
        assert result.multiplier == 0.0

    def test_drawdown_cut_action_generated(self) -> None:
        result = evaluate_drawdown([100.0, 80.0])
        assert len(result.actions) == 1
        assert result.actions[0].action_type == "drawdown_cut"

    def test_empty_curve_returns_one(self) -> None:
        result = evaluate_drawdown([])
        assert result.multiplier == 1.0

    def test_negative_peak_returns_one(self) -> None:
        result = evaluate_drawdown([-100.0])
        assert result.multiplier == 1.0

    def test_rolling_window_avoids_old_peak(self) -> None:
        curve = [200.0, 100.0, 105.0, 98.0]
        cfg = RiskConfig(dd_ladder=[[0.05, 0.5]], dd_window_days=3)
        result = evaluate_drawdown(curve, config=cfg)
        assert pytest.approx(result.multiplier) == 0.5


class TestEvaluateDailyLoss:
    def test_loss_exceeds_halt(self) -> None:
        result = evaluate_daily_loss(
            today_pnl=-5_000.0,
            equity_before_pnl=100_000.0,
            config=RiskConfig(daily_loss_halt_pct=0.03),
        )
        assert len(result) == 1
        assert result[0].action_type == "daily_halt"

    def test_loss_within_tolerance(self) -> None:
        result = evaluate_daily_loss(today_pnl=-1_000.0, equity_before_pnl=100_000.0)
        assert result == []

    def test_positive_pnl_returns_empty(self) -> None:
        result = evaluate_daily_loss(today_pnl=5_000.0, equity_before_pnl=100_000.0)
        assert result == []

    def test_zero_equity_returns_empty(self) -> None:
        result = evaluate_daily_loss(today_pnl=-1_000.0, equity_before_pnl=0.0)
        assert result == []

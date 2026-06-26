"""Unit tests for fill model (domain.fills)."""

from datetime import date, datetime

from alpha_quant.domain.fills import (
    FillConfig,
    apply_corporate_action,
    fill_entry_order,
    fill_partial_take,
    fill_stop_loss,
    make_fill_id,
)
from alpha_quant.domain.models import Bar, CorporateAction, Order, Position, Quote


def _bar(open_v: float = 100.0, low: float = 95.0, high: float | None = None) -> Bar:
    return Bar(
        symbol="AAPL",
        date=date(2026, 6, 11),
        open=open_v,
        high=high or max(open_v, 105.0),
        low=min(low, open_v, 100.0),
        close=100.0,
        volume=1_000_000,
    )


def _order(
    action: str = "buy",
    quantity: float = 100.0,
    order_id: str = "ord-001",
) -> Order:
    return Order(
        order_id=order_id,
        symbol="AAPL",
        action=action,
        quantity=quantity,
        order_type="market",
        status="submitted",
    )


def _position(
    quantity: float = 100.0,
    avg_cost: float = 100.0,
    stop_price: float | None = 90.0,
) -> Position:
    return Position(
        symbol="AAPL",
        quantity=quantity,
        entry_price=avg_cost,
        avg_cost=avg_cost,
        current_price=avg_cost,
        stop_price=stop_price,
        market_value=quantity * avg_cost,
    )


def _quote(bid: float = 99.0, ask: float = 101.0) -> Quote:
    return Quote(
        symbol="AAPL",
        timestamp=datetime(2026, 6, 11, 9, 30),
        bid=bid,
        ask=ask,
    )


class TestMakeFillId:
    def test_deterministic(self) -> None:
        a = make_fill_id("ord-001", date(2026, 6, 11))
        b = make_fill_id("ord-001", date(2026, 6, 11))
        assert a == b

    def test_different_order_id(self) -> None:
        a = make_fill_id("ord-001", date(2026, 6, 11))
        b = make_fill_id("ord-002", date(2026, 6, 11))
        assert a != b

    def test_different_date(self) -> None:
        a = make_fill_id("ord-001", date(2026, 6, 11))
        b = make_fill_id("ord-001", date(2026, 6, 12))
        assert a != b


class TestFillEntryOrder:
    def test_normal_fill(self) -> None:
        order = _order()
        bar = _bar()
        fill = fill_entry_order(order, bar, prev_close=99.9)
        assert fill is not None
        assert fill.symbol == "AAPL"
        assert fill.quantity == 100.0
        assert fill.price > 0
        assert fill.order_id == "ord-001"

    def test_wrong_action_returns_none(self) -> None:
        order = _order(action="sell")
        fill = fill_entry_order(order, _bar(), prev_close=99.0)
        assert fill is None

    def test_gap_too_large_returns_none(self) -> None:
        order = _order()
        bar = _bar(open_v=110.0)
        fill = fill_entry_order(order, bar, prev_close=100.0)
        assert fill is None

    def test_zero_prev_close_skips_gap_check(self) -> None:
        order = _order()
        bar = _bar(open_v=110.0)
        fill = fill_entry_order(order, bar, prev_close=0.0)
        assert fill is not None

    def test_quote_slippage_applied(self) -> None:
        order = _order()
        bar = _bar(open_v=100.0)
        fill = fill_entry_order(order, bar, prev_close=99.9, quote=_quote(bid=98.0, ask=102.0))
        assert fill is not None
        assert fill.price > 100.0

    def test_gap_at_threshold_passes(self) -> None:
        order = _order()
        bar = _bar(open_v=100.5)
        fill = fill_entry_order(order, bar, prev_close=100.0)
        assert fill is not None

    def test_gap_above_threshold_fails(self) -> None:
        order = _order()
        bar = _bar(open_v=103.0)
        fill = fill_entry_order(order, bar, prev_close=100.0)
        assert fill is None  # 3% gap > 2% max_gap_pct

    def test_gap_exactly_at_threshold_passes(self) -> None:
        order = _order()
        bar = _bar(open_v=100.5)
        fill = fill_entry_order(order, bar, prev_close=100.0)
        assert fill is not None

    def test_gap_just_above_threshold_fails(self) -> None:
        order = _order()
        bar = _bar(open_v=100.5)
        cfg = FillConfig(max_gap_pct=0.004)
        fill = fill_entry_order(order, bar, prev_close=100.0, config=cfg)
        assert fill is None

    def test_gap_above_custom_threshold_fails(self) -> None:
        order = _order()
        bar = _bar(open_v=100.2)
        cfg = FillConfig(max_gap_pct=0.001)
        fill = fill_entry_order(order, bar, prev_close=100.0, config=cfg)
        assert fill is None

    def test_partial_fill_reduces_quantity(self) -> None:
        order = _order(quantity=100.0)
        bar = _bar(open_v=100.2)
        cfg = FillConfig(max_fill_pct=0.5)
        fill = fill_entry_order(order, bar, prev_close=99.9, config=cfg)
        assert fill is not None
        assert fill.quantity == 50


class TestFillStopLoss:
    def test_stop_hit(self) -> None:
        pos = _position(stop_price=90.0)
        bar = _bar(low=85.0)
        fill = fill_stop_loss(pos, bar, order_id="stop-001")
        assert fill is not None
        assert fill.quantity < 0
        assert fill.price > 0

    def test_stop_not_touched(self) -> None:
        pos = _position(stop_price=90.0)
        bar = _bar(low=92.0)
        fill = fill_stop_loss(pos, bar, order_id="stop-001")
        assert fill is None

    def test_no_stop_price(self) -> None:
        pos = _position(stop_price=None)
        fill = fill_stop_loss(pos, _bar(), order_id="stop-001")
        assert fill is None

    def test_negative_quantity(self) -> None:
        pos = _position(quantity=-100.0, stop_price=90.0)
        bar = _bar(low=85.0)
        fill = fill_stop_loss(pos, bar, order_id="stop-001")
        assert fill is not None
        assert fill.quantity > 0


class TestFillPartialTake:
    def test_normal_partial(self) -> None:
        pos = _position(quantity=100.0)
        fill = fill_partial_take(pos, _bar(), order_id="part-001")
        assert fill is not None
        assert fill.quantity == -50
        assert fill.price > 0

    def test_small_position_returns_none(self) -> None:
        pos = _position(quantity=0)
        fill = fill_partial_take(pos, _bar(), order_id="part-001")
        assert fill is None

    def test_quantity_1_returns_none(self) -> None:
        pos = _position(quantity=1)
        fill = fill_partial_take(pos, _bar(), order_id="part-001")
        assert fill is None


class TestApplyCorporateAction:
    def test_stock_split(self) -> None:
        pos = _position(quantity=100.0, avg_cost=200.0)
        ca = CorporateAction(
            symbol="AAPL",
            effective_date=date(2026, 6, 11),
            action_type="split",
            ratio=4.0,
        )
        updated = apply_corporate_action(pos, ca)
        assert updated.quantity == 400
        assert updated.avg_cost == 50.0

    def test_split_with_none_ratio_returns_unchanged(self) -> None:
        pos = _position(quantity=100.0, avg_cost=200.0)
        ca = CorporateAction(
            symbol="AAPL",
            effective_date=date(2026, 6, 11),
            action_type="split",
            ratio=None,
        )
        updated = apply_corporate_action(pos, ca)
        assert updated.quantity == 100.0

    def test_dividend(self) -> None:
        pos = _position(quantity=100.0, avg_cost=200.0)
        ca = CorporateAction(
            symbol="AAPL",
            effective_date=date(2026, 6, 11),
            action_type="dividend",
            amount=5.0,
        )
        updated = apply_corporate_action(pos, ca)
        assert updated.avg_cost == 195.0

    def test_dividend_with_none_amount_returns_unchanged(self) -> None:
        pos = _position(quantity=100.0, avg_cost=200.0)
        ca = CorporateAction(
            symbol="AAPL",
            effective_date=date(2026, 6, 11),
            action_type="dividend",
            amount=None,
        )
        updated = apply_corporate_action(pos, ca)
        assert updated.avg_cost == 200.0

    def test_dividend_capped_at_zero(self) -> None:
        pos = _position(quantity=100.0, avg_cost=2.0)
        ca = CorporateAction(
            symbol="AAPL",
            effective_date=date(2026, 6, 11),
            action_type="dividend",
            amount=5.0,
        )
        updated = apply_corporate_action(pos, ca)
        assert updated.avg_cost >= 0.0

    def test_unknown_action_returns_unchanged(self) -> None:
        pos = _position(quantity=100.0, avg_cost=200.0)
        ca = CorporateAction(
            symbol="AAPL",
            effective_date=date(2026, 6, 11),
            action_type="merger",
            ratio=0.5,
        )
        updated = apply_corporate_action(pos, ca)
        assert updated.quantity == 100.0

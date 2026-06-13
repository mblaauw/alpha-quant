"""Unit tests for FakeBroker lifecycle."""

from alpha_quant.adapters.fake.fake_broker import FakeBroker
from alpha_quant.domain.models import Order


class TestFakeBroker:
    def test_submit_order_creates_fill(self) -> None:
        broker = FakeBroker(initial_cash=100_000.0)
        order = Order(
            order_id="",
            symbol="AAPL",
            action="buy",
            quantity=100.0,
            order_type="market",
            status="submitted",
        )
        filled = broker.submit_order(order)
        assert filled.status == "filled"
        assert filled.filled_quantity == 100.0
        positions = broker.positions()
        assert len(positions) == 1
        assert positions[0].symbol == "AAPL"

    def test_portfolio_after_order(self) -> None:
        broker = FakeBroker(initial_cash=100_000.0)
        order = Order(
            order_id="",
            symbol="AAPL",
            action="buy",
            quantity=100.0,
            order_type="market",
            status="submitted",
            limit_price=150.0,
        )
        broker.submit_order(order)
        pf = broker.portfolio()
        assert pf["cash"] < 100_000.0
        assert pf["equity"] == 100_000.0

    def test_cancel_order(self) -> None:
        broker = FakeBroker()
        order = Order(
            order_id="ord-001",
            symbol="AAPL",
            action="buy",
            quantity=100.0,
            order_type="market",
            status="submitted",
        )
        broker.submit_order(order)
        assert broker.cancel_order("ord-001") is True
        assert broker.cancel_order("nonexistent") is False

    def test_fills_since(self) -> None:
        broker = FakeBroker()
        order = Order(
            order_id="",
            symbol="AAPL",
            action="buy",
            quantity=100.0,
            order_type="market",
            status="submitted",
        )
        broker.submit_order(order)
        all_fills = broker.fills()
        assert len(all_fills) == 1

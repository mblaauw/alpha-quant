from datetime import date, datetime

import pytest
from pydantic import ValidationError

from domain.models import Order


class TestOrderValidation:
    def test_valid_order_default(self) -> None:
        o = Order(
            order_id="ord-001",
            symbol="AAPL",
            action="buy",
            quantity=100.0,
            order_type="market",
            status="submitted",
        )
        assert o.filled_quantity is None
        assert o.fill_date is None

    def test_fill_quantity_less_than_quantity(self) -> None:
        o = Order(
            order_id="ord-002",
            symbol="AAPL",
            action="buy",
            quantity=100.0,
            order_type="limit",
            limit_price=150.0,
            status="filled",
            fill_date=datetime(2026, 6, 11),
            filled_quantity=100.0,
            avg_fill_price=149.5,
        )
        assert o.filled_quantity == 100.0

    def test_fill_quantity_equal_to_quantity(self) -> None:
        o = Order(
            order_id="ord-003",
            symbol="MSFT",
            action="buy",
            quantity=50.0,
            order_type="market",
            status="filled",
            fill_date=datetime(2026, 6, 11),
            filled_quantity=50.0,
        )
        assert o.filled_quantity == 50.0

    def test_fill_quantity_exceeds_quantity_raises_error(self) -> None:
        with pytest.raises(ValidationError, match="filled_quantity"):
            Order(
                order_id="ord-004",
                symbol="AAPL",
                action="buy",
                quantity=100.0,
                order_type="market",
                status="filled",
                fill_date=datetime(2026, 6, 11),
                filled_quantity=150.0,
            )

    def test_partial_fill_valid(self) -> None:
        o = Order(
            order_id="ord-005",
            symbol="GOOGL",
            action="buy",
            quantity=200.0,
            order_type="limit",
            limit_price=180.0,
            status="partially_filled",
            submitted_at=datetime(2026, 6, 10),
            fill_date=datetime(2026, 6, 11),
            filled_quantity=75.0,
            avg_fill_price=179.8,
        )
        assert o.filled_quantity == 75.0
        assert o.submitted_at == datetime(2026, 6, 10)

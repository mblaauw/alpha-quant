"""Integration tests for PaperPortfolio lifecycle."""

from datetime import date
from pathlib import Path

from alpha_quant.app.paper import PaperPortfolio
from alpha_quant.app.store import CanonicalStore
from alpha_quant.domain.models import Bar, Order


def test_full_entry_fill_mark_cycle(tmp_path: Path) -> None:
    store = CanonicalStore(base_path=tmp_path)
    portfolio = PaperPortfolio(store, run_id="test-run")
    portfolio.initialize(100_000.0, date(2025, 1, 1))

    bar = Bar(
        symbol="AAPL",
        date=date(2025, 1, 2),
        open=100.3,
        high=105.0,
        low=95.0,
        close=101.0,
        volume=1_000_000,
    )
    order = Order(
        order_id="ord-001",
        symbol="AAPL",
        action="buy",
        quantity=100.0,
        order_type="market",
        status="submitted",
    )

    result = portfolio.process_entry_orders(
        orders=[order],
        decision_ids={"AAPL": "dec-001"},
        bar=bar,
        prev_close=99.9,
    )
    assert len(result.fills) == 1
    assert result.fills[0].symbol == "AAPL"
    assert len(result.violations) == 0

    positions = store.load_positions()
    assert len(positions) == 1
    assert positions[0].quantity == 100.0

    snap = portfolio.mark_to_market(date(2025, 1, 2), {"AAPL": 102.0})
    assert snap.equity > 100_000.0
    assert snap.cash < 100_000.0


def test_stop_loss_exit(tmp_path: Path) -> None:
    store = CanonicalStore(base_path=tmp_path)
    portfolio = PaperPortfolio(store, run_id="test-run")
    portfolio.initialize(100_000.0, date(2025, 1, 1))

    bar = Bar(
        symbol="AAPL",
        date=date(2025, 1, 2),
        open=100.3,
        high=105.0,
        low=95.0,
        close=101.0,
        volume=1_000_000,
    )
    order = Order(
        order_id="ord-001",
        symbol="AAPL",
        action="buy",
        quantity=100.0,
        order_type="market",
        status="submitted",
    )

    entry_result = portfolio.process_entry_orders(
        orders=[order], decision_ids={"AAPL": "dec-001"}, bar=bar, prev_close=99.9
    )
    assert len(entry_result.fills) == 1

    positions = store.load_positions()
    assert len(positions) == 1
    pos = positions[0].model_copy(update={"stop_price": 90.0})
    store.save_position(pos)

    from alpha_quant.domain.risk import RiskAction

    risk_result = portfolio.process_risk_actions(
        actions=[RiskAction(action_type="stop", symbol="AAPL", shares=100.0, reason="stop hit")],
        bar=Bar(
            symbol="AAPL",
            date=date(2025, 1, 3),
            open=85.0,
            high=86.0,
            low=84.0,
            close=85.0,
            volume=1_000_000,
        ),
    )
    assert len(risk_result.fills) >= 1

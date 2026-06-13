"""Integration tests for CanonicalStore round-trip (Parquet + DuckDB)."""

from datetime import date
from pathlib import Path

from alpha_quant.app.store import CanonicalStore
from alpha_quant.domain.journal import JournalEntry
from alpha_quant.domain.models import Bar, Decision, Order, Position


def test_bars_round_trip(tmp_path: Path) -> None:
    store = CanonicalStore(base_path=tmp_path)
    bars = [
        Bar(
            symbol="AAPL",
            date=date(2025, 1, 1),
            open=100.0,
            high=105.0,
            low=95.0,
            close=101.0,
            volume=1_000_000,
        ),
        Bar(
            symbol="AAPL",
            date=date(2025, 1, 2),
            open=101.0,
            high=106.0,
            low=96.0,
            close=102.0,
            volume=1_100_000,
        ),
    ]
    store.save_bars("AAPL", bars)
    loaded = store.load_bars("AAPL", date(2025, 1, 1), date(2025, 1, 2))
    assert len(loaded) == 2
    assert loaded[0].symbol == "AAPL"
    assert loaded[0].close == 102.0
    assert loaded[1].close == 101.0


def test_positions_round_trip(tmp_path: Path) -> None:
    store = CanonicalStore(base_path=tmp_path)
    pos = Position(symbol="AAPL", quantity=100.0, avg_cost=100.0, market_value=10_000.0)
    store.save_position(pos)
    loaded = store.load_positions()
    assert len(loaded) == 1
    assert loaded[0].symbol == "AAPL"
    assert loaded[0].quantity == 100.0


def test_journal_round_trip(tmp_path: Path) -> None:
    store = CanonicalStore(base_path=tmp_path)
    entry = JournalEntry(date=date(2025, 1, 1), content="test entry")
    store.save_journal(entry)
    loaded = store.load_journal(date(2025, 1, 1))
    assert loaded is not None
    assert loaded.content == "test entry"


def test_decision_round_trip(tmp_path: Path) -> None:
    store = CanonicalStore(base_path=tmp_path)
    d = Decision(symbol="AAPL", date=date(2025, 1, 1), action="enter", confidence=0.8)
    store.save_decision(d)
    loaded = store.load_decisions("AAPL", date(2025, 1, 1))
    assert len(loaded) == 1
    assert loaded[0].action == "enter"


def test_order_round_trip(tmp_path: Path) -> None:
    store = CanonicalStore(base_path=tmp_path)
    o = Order(
        order_id="ord-001",
        symbol="AAPL",
        action="buy",
        quantity=100.0,
        order_type="market",
        status="submitted",
    )
    store.save_order(o)
    loaded = store.load_order("ord-001")
    assert loaded is not None
    assert loaded.quantity == 100.0

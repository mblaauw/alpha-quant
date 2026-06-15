"""Integration tests for CanonicalStore round-trip (Parquet + DuckDB)."""

from datetime import date
from pathlib import Path

from alpha_quant.app.store import CanonicalStore
from alpha_quant.domain.journal import JournalEntry
from alpha_quant.domain.models import (
    Bar,
    CorporateAction,
    Decision,
    EarningsEntry,
    FundamentalsSnapshot,
    InsiderTransaction,
    MentionCount,
    Order,
    Position,
)


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


def test_bars_round_trip_with_fetch_id(tmp_path: Path) -> None:
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
            fetch_id="abc123",
        ),
        Bar(
            symbol="AAPL",
            date=date(2025, 1, 2),
            open=101.0,
            high=106.0,
            low=96.0,
            close=102.0,
            volume=1_100_000,
            fetch_id=None,
        ),
    ]
    store.save_bars("AAPL", bars)
    loaded = store.load_bars("AAPL", date(2025, 1, 1), date(2025, 1, 2))
    assert len(loaded) == 2
    assert loaded[0].fetch_id is None  # latest bar has no fetch_id
    assert loaded[1].fetch_id == "abc123"


def test_fundamentals_round_trip_with_fetch_id(tmp_path: Path) -> None:
    store = CanonicalStore(base_path=tmp_path)
    snap = FundamentalsSnapshot(
        symbol="AAPL",
        as_of_date=date(2025, 1, 1),
        market_cap=1e12,
        fetch_id="def456",
    )
    store.save_fundamentals("AAPL", [snap])
    loaded = store.load_fundamentals("AAPL")
    assert len(loaded) >= 1
    assert loaded[0].fetch_id == "def456"


def test_insider_round_trip_with_fetch_id(tmp_path: Path) -> None:
    store = CanonicalStore(base_path=tmp_path)
    tx = InsiderTransaction(
        symbol="AAPL",
        owner="CEO",
        transaction_type="Buy",
        shares_traded=1000.0,
        fetch_id="ghi789",
    )
    store.save_insider_transactions("AAPL", [tx])
    loaded = store.load_insider_transactions("AAPL")
    assert len(loaded) >= 1
    assert loaded[0].fetch_id == "ghi789"


def test_mentions_round_trip_with_fetch_id(tmp_path: Path) -> None:
    store = CanonicalStore(base_path=tmp_path)
    m = MentionCount(
        symbol="AAPL",
        mention_date=date(2025, 1, 1),
        source="reddit",
        count=10,
        fetch_id="jkl012",
    )
    store.save_mentions("AAPL", [m])
    loaded = store.load_mentions("AAPL")
    assert len(loaded) >= 1
    assert loaded[0].fetch_id == "jkl012"


def test_earnings_round_trip_with_fetch_id(tmp_path: Path) -> None:
    store = CanonicalStore(base_path=tmp_path)
    e = EarningsEntry(
        symbol="AAPL",
        date=date(2025, 1, 1),
        fetch_id="mno345",
    )
    store.save_earnings("AAPL", [e])
    loaded = store.load_earnings("AAPL")
    assert len(loaded) >= 1
    assert loaded[0].fetch_id == "mno345"


def test_corp_actions_round_trip_with_fetch_id(tmp_path: Path) -> None:
    store = CanonicalStore(base_path=tmp_path)
    ca = CorporateAction(
        symbol="AAPL",
        effective_date=date(2025, 1, 1),
        action_type="SPLIT",
        ratio=2.0,
        fetch_id="pqr678",
    )
    store.save_corp_actions("AAPL", [ca])
    loaded = store.load_corp_actions("AAPL")
    assert len(loaded) >= 1
    assert loaded[0].fetch_id == "pqr678"

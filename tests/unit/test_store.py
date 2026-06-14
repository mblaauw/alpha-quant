"""Unit tests for CanonicalStore save/load round-trips."""

from datetime import date
from pathlib import Path

import pytest

from alpha_quant.app.store import CanonicalStore
from alpha_quant.domain.journal import JournalEntry
from alpha_quant.domain.models import (
    EarningsEntry,
    FundamentalsSnapshot,
    InsiderTransaction,
    MentionCount,
)


def test_transaction_rollback_on_exception(tmp_path: Path) -> None:
    store = CanonicalStore(base_path=tmp_path)
    entry = JournalEntry(date=date(2025, 1, 1), content="test-rollback")
    try:
        with store.transaction():
            store.save_journal(entry)
            msg = "1/0"
            raise RuntimeError(msg)
    except RuntimeError:
        pass
    loaded = store.load_journal(entry.date)
    assert loaded is None, "journal entry should not exist after rollback"


def test_transaction_commit_on_success(tmp_path: Path) -> None:
    store = CanonicalStore(base_path=tmp_path)
    entry = JournalEntry(date=date(2025, 1, 1), content="test-commit")
    with store.transaction():
        store.save_journal(entry)
    loaded = store.load_journal(entry.date)
    assert loaded is not None, "journal entry should exist after commit"
    assert loaded.content == "test-commit"


def test_save_and_load_fundamentals(tmp_path: Path) -> None:
    store = CanonicalStore(base_path=tmp_path)
    snap = FundamentalsSnapshot(
        symbol="AAPL",
        as_of_date=date(2025, 6, 1),
        market_cap=3_000_000_000_000.0,
        revenue=400_000_000_000.0,
        operating_cash_flow=120_000_000_000.0,
        total_debt=150_000_000_000.0,
        total_equity=50_000_000_000.0,
        sector="Technology",
        industry="Consumer Electronics",
    )
    store.save_fundamentals("AAPL", [snap])
    loaded = store.load_fundamentals("AAPL")
    assert len(loaded) == 1
    assert loaded[0].market_cap == 3_000_000_000_000.0
    assert loaded[0].sector == "Technology"


def test_save_and_load_insider_transactions(tmp_path: Path) -> None:
    store = CanonicalStore(base_path=tmp_path)
    txn = InsiderTransaction(
        symbol="AAPL",
        filing_date=date(2025, 6, 1),
        transaction_date=date(2025, 5, 30),
        transaction_type="P-Purchase",
        owner="Tim Cook",
        title="CEO",
        shares_traded=10_000.0,
        price=180.0,
        shares_held=1_000_000.0,
        trade_signal="cluster_buy",
    )
    store.save_insider_transactions("AAPL", [txn])
    loaded = store.load_insider_transactions("AAPL")
    assert len(loaded) == 1
    assert loaded[0].owner == "Tim Cook"
    assert loaded[0].shares_traded == 10_000.0


def test_save_and_load_mentions(tmp_path: Path) -> None:
    store = CanonicalStore(base_path=tmp_path)
    mention = MentionCount(
        symbol="AAPL",
        mention_date=date(2025, 6, 1),
        source="wallstreetbets",
        count=42,
    )
    store.save_mentions("AAPL", [mention])
    loaded = store.load_mentions("AAPL")
    assert len(loaded) == 1
    assert loaded[0].source == "wallstreetbets"
    assert loaded[0].count == 42


def test_save_and_load_earnings(tmp_path: Path) -> None:
    store = CanonicalStore(base_path=tmp_path)
    entry = EarningsEntry(
        symbol="AAPL",
        date=date(2025, 5, 1),
        eps_estimate=2.0,
        eps_actual=2.5,
    )
    store.save_earnings("AAPL", [entry])
    loaded = store.load_earnings("AAPL")
    assert len(loaded) == 1
    assert loaded[0].eps_actual == 2.5

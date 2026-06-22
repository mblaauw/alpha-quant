"""Unit tests for CanonicalStore save/load round-trips."""

from datetime import date
from pathlib import Path

from app.store import CanonicalStore
from domain.journal import JournalEntry


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

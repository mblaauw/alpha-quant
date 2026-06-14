"""Tests for content-addressed vault (append-only writes)."""

from pathlib import Path

from alpha_quant.app.vault import Vault


def test_append_only_duplicate_returns_same_fetch_id(tmp_path: Path) -> None:
    """Writing the same payload twice returns the same fetch_id (dedup)."""
    vault = Vault(tmp_path)
    data = b'{"price": 100.5, "volume": 50000}'
    fid1 = vault.store("test_source", "test_endpoint", {"symbol": "AAPL"}, data)
    fid2 = vault.store("test_source", "test_endpoint", {"symbol": "AAPL"}, data)
    assert fid1 == fid2, "same payload should produce same fetch_id"


def test_different_payloads_different_fetch_ids(tmp_path: Path) -> None:
    """Different payloads produce different fetch_ids."""
    vault = Vault(tmp_path)
    fid1 = vault.store("src", "ep", {"q": "a"}, b"data one")
    fid2 = vault.store("src", "ep", {"q": "a"}, b"data two")
    assert fid1 != fid2, "different payloads should produce different fetch_ids"


def test_append_only_rewrite_does_not_create_new_blob(tmp_path: Path) -> None:
    """Rewriting the same data does not create additional blob files."""
    vault = Vault(tmp_path)
    data = b"some content"
    fid1 = vault.store("src", "ep", {"k": "v"}, data)
    fid2 = vault.store("src", "ep", {"k": "v"}, data)
    assert fid1 == fid2
    blob_files = list(tmp_path.rglob("*.zst"))
    assert len(blob_files) == 1, "only one blob file should exist for deduped data"

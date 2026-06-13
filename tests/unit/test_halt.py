from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path

import pytest

import alpha_quant.app.halt as halt_mod
from alpha_quant.app.halt import clear_halt, halt_file_path, is_halted, read_halt, write_halt


@pytest.fixture(autouse=True)
def _clean_halt(tmp_path: Path) -> Generator[None]:
    test_path = tmp_path / "data" / ".HALT"
    test_path.parent.mkdir(parents=True, exist_ok=True)
    original = halt_mod.HALT_PATH
    halt_mod.HALT_PATH = test_path
    yield
    halt_mod.HALT_PATH = original


def _halt_path() -> Path:
    return halt_mod.HALT_PATH


class TestHaltFilePath:
    def test_returns_path(self) -> None:
        p = halt_file_path()
        assert p.name == ".HALT"
        assert "data" in str(p)


class TestIsHalted:
    def test_returns_false_when_no_file(self) -> None:
        assert is_halted() is False

    def test_returns_true_when_file_exists(self) -> None:
        _halt_path().write_text("{}")
        assert is_halted() is True


class TestWriteHalt:
    def test_writes_reason_and_timestamp(self) -> None:
        write_halt(reason="test halt")
        assert _halt_path().exists()
        data = json.loads(_halt_path().read_text())
        assert data["reason"] == "test halt"
        assert "timestamp" in data

    def test_includes_run_id_when_provided(self) -> None:
        write_halt(reason="emergency", run_id="abc123")
        data = json.loads(_halt_path().read_text())
        assert data["run_id"] == "abc123"

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        deep = tmp_path / "a" / "b" / ".HALT"
        original = halt_mod.HALT_PATH
        halt_mod.HALT_PATH = deep
        write_halt(reason="deep")
        assert deep.exists()
        halt_mod.HALT_PATH = original


class TestReadHalt:
    def test_returns_none_when_no_file(self) -> None:
        assert read_halt() is None

    def test_returns_contents_when_file_exists(self) -> None:
        write_halt(reason="maintenance")
        data = read_halt()
        assert data is not None
        assert data["reason"] == "maintenance"
        assert "timestamp" in data

    def test_returns_fallback_on_corrupt_json(self) -> None:
        _halt_path().write_text("not json")
        data = read_halt()
        assert data is not None
        assert data["reason"] == "unknown"


class TestClearHalt:
    def test_removes_file(self) -> None:
        write_halt(reason="test")
        assert _halt_path().exists()
        assert clear_halt() is True
        assert not _halt_path().exists()

    def test_returns_false_when_no_file(self) -> None:
        assert clear_halt() is False

"""Tests for the Typer-based CLI."""

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_quant.application.cli import app

runner = CliRunner()


@pytest.fixture
def tmp_config(tmp_path: Path) -> Generator[Path]:
    config_dir = tmp_path / ".alpha-quant"
    config_dir.mkdir()
    config_path = config_dir / "config.toml"
    yield config_path


def _with_env(name: str, value: str) -> Generator[None]:
    old = os.environ.get(name)
    os.environ[name] = value
    yield
    if old is None:
        del os.environ[name]
    else:
        os.environ[name] = old


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "alpha-quant" in result.stdout


class TestDBCommands:
    def test_help_shows_db_commands(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert "Database" in result.stdout

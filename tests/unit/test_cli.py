"""Tests for the Typer-based CLI."""

import json
import os
from collections.abc import Generator
from datetime import date, timedelta
from pathlib import Path
from textwrap import dedent

import pytest
from typer.testing import CliRunner

from app.cli import _parse_date, app

runner = CliRunner()

# ── Helpers ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def config_file(tmp_path: Path) -> Path:
    """Create a minimal valid config.toml."""
    cfg = dedent("""\
        [bootstrap]
        symbols = ["AAPL", "MSFT"]
        history_years = 3
        include_benchmarks = ["SPY"]

        [data]
        mode = "fixture"
        indicator_state = true
        staleness_halt_hours = 30
        fixture_version = "v1"

        [universe]
        min_price = 5.0
        min_adv_usd = 5_000_000
        index_base = "sp500_plus_midcap400"

        [portfolio]
        max_positions = 8
        max_position_pct = 0.15
        max_gross_exposure = 0.80
        risk_per_trade_pct = 0.01
        max_sector_positions = 2

        [paper]
        starting_equity = 100000
        slippage_bps = 5
        spread_model = "half_spread_estimate"

        [risk]
        stop_atr_mult = 2.0
        trail_after_r = 1.0
        partial_take_at_r = 2.0
        time_stop_days = 30
        dd_ladder = [[0.10, 0.5], [0.15, 0.0]]
        daily_loss_halt_pct = 0.03

        [shadow]
        books = ["RULES_ONLY"]

        [llm]
        provider = "openrouter"
        model = "test-model"
        base_url = ""
        timeout_s = 30

        [education]
        level = "beginner"
        concept_repeat_limit = 3

        [eodhd]
        api_key = ""
        base_url = "https://eodhd.com/api"

        [alpaca]
        api_key = ""
        secret_key = ""
        base_url = "https://data.alpaca.markets"

        [connector]
        user_agent = "AlphaQuant/0.2.0 (test)"
        tokens_per_second = 10.0
        max_burst = 20.0
        default_timeout_s = 30.0

        [dashboard]
        host = "localhost"
        port = 8501
        refresh_seconds = 60
    """)
    path = tmp_path / "config.toml"
    path.write_text(cfg)
    return path


@pytest.fixture
def isolated_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Create an isolated temp dir and chdir into it."""
    cwd = Path.cwd()
    os.chdir(str(tmp_path))
    yield tmp_path
    os.chdir(str(cwd))


# ── Smoke Tests ──────────────────────────────────────────────────────────────────


class TestSmoke:
    """Basic smoke tests — no config needed."""

    def test_help_exits_0(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_help_lists_all_commands(self) -> None:
        result = runner.invoke(app, ["--help"])
        for cmd in [
            "run",
            "replay",
            "backtest",
            "bootstrap",
            "journal",
            "ask",
            "report",
            "status",
            "halt",
            "schedule",
            "backup",
        ]:
            assert cmd in result.output, f"Command '{cmd}' not found in help"

    def test_version(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "alpha-quant" in result.output

    def test_no_args_shows_help(self) -> None:
        result = runner.invoke(app, [])
        assert "Usage:" in result.output or "Commands:" in result.output

    def test_unknown_command_errors(self) -> None:
        result = runner.invoke(app, ["nonsense"])
        assert result.exit_code != 0

    def test_each_command_help(self) -> None:
        for cmd in [
            "run",
            "replay",
            "backtest",
            "bootstrap",
            "journal",
            "ask",
            "report",
            "status",
            "halt",
            "schedule",
            "backup",
        ]:
            result = runner.invoke(app, [cmd, "--help"])
            assert result.exit_code == 0, f"'{cmd} --help' failed: {result.output}"
            assert cmd in result.output.lower() or cmd.capitalize() in result.output


# ── Relative Date Parsing ────────────────────────────────────────────────────────


class TestRelativeDateParsing:
    """Unit tests for _parse_date helper."""

    def test_7_days(self) -> None:
        expected = date.today() - timedelta(days=7)
        assert _parse_date("7d") == expected

    def test_30_days(self) -> None:
        expected = date.today() - timedelta(days=30)
        assert _parse_date("30d") == expected

    def test_3_months(self) -> None:
        expected = date.today() - timedelta(days=90)
        assert _parse_date("3m") == expected

    def test_1_year(self) -> None:
        expected = date.today() - timedelta(days=365)
        assert _parse_date("1y") == expected

    def test_iso_date(self) -> None:
        assert _parse_date("2024-01-15") == date(2024, 1, 15)

    def test_whitespace_stripped(self) -> None:
        assert _parse_date("  7d  ") == date.today() - timedelta(days=7)

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            _parse_date("not-a-date")

    def test_invalid_unit_falls_through(self) -> None:
        """'7w' matches regex but 'w' is not valid => falls to fromisoformat => error."""
        with pytest.raises(ValueError):
            _parse_date("7w")


# ── Config & Error Handling ──────────────────────────────────────────────────────


class TestConfigErrors:
    """Tests that require config file interaction."""

    def test_nonexistent_config_shows_error_panel(self) -> None:
        result = runner.invoke(app, ["--config", "/nonexistent/path/config.toml", "status"])
        assert result.exit_code != 0

    def test_valid_config_with_status(self, config_file: Path) -> None:
        """status with valid config succeeds."""
        result = runner.invoke(app, ["--config", str(config_file), "status"])
        assert result.exit_code == 0

    def test_verbose_flag_shows_config(self, config_file: Path) -> None:
        result = runner.invoke(app, ["--config", str(config_file), "--verbose", "status"])
        assert result.exit_code == 0
        assert "AAPL" in result.output  # config content shown

    def test_halt_resume_when_not_halted(self, isolated_dir: Path) -> None:
        """halt --resume when no halt file exists shows error."""
        result = runner.invoke(app, ["halt", "--resume"])
        assert result.exit_code == 0  # error shown via panel, not a crash
        assert "not" in result.output.lower() or "Not" in result.output


# ── Command-specific Tests ───────────────────────────────────────────────────────


class TestHaltCommand:
    """Tests for halt/resume commands."""

    def test_halt_with_reason(self, isolated_dir: Path) -> None:
        result = runner.invoke(app, ["halt", "testing", "halt"])
        assert result.exit_code == 0
        assert "Halted" in result.output or "Halt" in result.output

    def test_halt_default_reason(self, isolated_dir: Path) -> None:
        result = runner.invoke(app, ["halt"])
        assert result.exit_code == 0

    def test_halt_then_resume(self, isolated_dir: Path) -> None:
        runner.invoke(app, ["halt", "test"])
        result = runner.invoke(app, ["halt", "--resume", "--yes"])
        assert result.exit_code == 0
        assert "Resumed" in result.output or "cleared" in result.output


class TestStatusCommand:
    """Tests for status command."""

    def test_status_json_output(self, config_file: Path) -> None:
        result = runner.invoke(app, ["--config", str(config_file), "status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)
        assert "halted" in data
        assert "portfolio" in data

    def test_status_show_config(self, config_file: Path) -> None:
        result = runner.invoke(app, ["--config", str(config_file), "status", "--show-config"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "bootstrap" in data


class TestBacktestCommand:
    """Tests for backtest command."""

    def test_backtest_requires_dates(self) -> None:
        result = runner.invoke(app, ["backtest"])
        assert result.exit_code != 0  # missing --from-date and --to-date

    def test_backtest_invalid_date_format(self, config_file: Path) -> None:
        result = runner.invoke(
            app,
            [
                "--config",
                str(config_file),
                "backtest",
                "--from-date",
                "not-a-date",
                "--to-date",
                "2024-01-31",
            ],
        )
        assert result.exit_code != 0


class TestReplayCommand:
    """Tests for replay command."""

    def test_replay_requires_dates(self) -> None:
        result = runner.invoke(app, ["replay"])
        assert result.exit_code != 0


class TestAskCommand:
    """Tests for ask command."""

    def test_ask_requires_query(self) -> None:
        result = runner.invoke(app, ["ask"])
        assert result.exit_code != 0

    def test_ask_short_query(self, config_file: Path) -> None:
        """Ask with a very short query doesn't crash in CLI layer."""
        result = runner.invoke(app, ["--config", str(config_file), "ask", "ATR"])
        assert result.exit_code in (0, 1)


class TestBackupCommand:
    """Tests for backup command."""

    def test_backup_accepts_prune_flag(self) -> None:
        """Just check the help text mentions --prune."""
        result = runner.invoke(app, ["backup", "--help"])
        assert result.exit_code == 0
        assert "prune" in result.output

    def test_backup_needs_state_db(self, isolated_dir: Path) -> None:
        """Without a state DB, backup fails gracefully."""
        os.makedirs("data", exist_ok=True)
        result = runner.invoke(app, ["backup"])
        assert result.exit_code != 0


# ── Output Format Tests ──────────────────────────────────────────────────────────


class TestOutputFormat:
    """Ensure Rich-formatted and plain-text outputs are correct."""

    def test_plain_status_output(self, config_file: Path) -> None:
        result = runner.invoke(app, ["--config", str(config_file), "status"])
        assert result.exit_code == 0
        assert "System Status" in result.output or "Halted" in result.output

    def test_json_status_is_valid_json(self, config_file: Path) -> None:
        result = runner.invoke(app, ["--config", str(config_file), "status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data["halted"], bool)

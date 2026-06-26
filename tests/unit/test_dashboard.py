from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pytest

from alpha_quant.application.dashboard.db import DashboardDB
from alpha_quant.application.dashboard.routes.concepts import (
    _parse_frontmatter,
    _strip_frontmatter,
)


class TestStripFrontmatter:
    def test_strips_yaml_frontmatter(self) -> None:
        md = "---\nid: atr\ntitle: ATR\n---\n\nBody content"
        assert _strip_frontmatter(md) == "Body content"

    def test_no_frontmatter(self) -> None:
        md = "Just body content"
        assert _strip_frontmatter(md) == "Just body content"

    def test_empty_string(self) -> None:
        assert _strip_frontmatter("") == ""

    def test_only_frontmatter(self) -> None:
        md = "---\nid: test\n---"
        assert _strip_frontmatter(md) == ""


class TestParseFrontmatter:
    def test_parses_frontmatter(self) -> None:
        result = _parse_frontmatter("---\nid: atr\ntitle: ATR Explained\n---\n\nContent")
        assert result["id"] == "atr"
        assert result["title"] == "ATR Explained"

    def test_no_frontmatter_returns_empty(self) -> None:
        assert _parse_frontmatter("No frontmatter") == {}

    def test_empty_string(self) -> None:
        assert _parse_frontmatter("") == {}


class TestDashboardDB:
    @pytest.fixture
    def seed(self, tmp_path: Path) -> Path:
        db_path = tmp_path / "state.db"
        conn = duckdb.connect(str(db_path))
        conn.execute(
            "CREATE TABLE positions ("
            "  symbol VARCHAR PRIMARY KEY,"
            "  quantity DOUBLE NOT NULL,"
            "  entry_price DOUBLE,"
            "  avg_cost DOUBLE NOT NULL,"
            "  current_price DOUBLE,"
            "  stop_price DOUBLE,"
            "  trail_price DOUBLE,"
            "  market_value DOUBLE,"
            "  unrealized_pl DOUBLE,"
            "  entry_date DATE,"
            "  high_since_entry DOUBLE,"
            "  partial_taken BOOLEAN"
            ")"
        )
        conn.execute(
            "CREATE TABLE equity_curve ("
            "  equity_date DATE NOT NULL,"
            "  equity DOUBLE NOT NULL,"
            "  cash DOUBLE NOT NULL DEFAULT 0,"
            "  regime VARCHAR,"
            "  book VARCHAR NOT NULL DEFAULT 'PAPER',"
            "  PRIMARY KEY (equity_date, book)"
            ")"
        )
        conn.execute(
            "CREATE TABLE journal_entries (  entry_date DATE PRIMARY KEY,  content TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE reports ("
            "  report_date DATE NOT NULL,"
            "  report_type VARCHAR NOT NULL,"
            "  content TEXT NOT NULL,"
            "  PRIMARY KEY (report_date, report_type)"
            ")"
        )
        conn.execute(
            "CREATE TABLE runs ("
            "  run_id VARCHAR PRIMARY KEY,"
            "  run_type VARCHAR NOT NULL,"
            "  config_hash VARCHAR NOT NULL,"
            "  start_ts TIMESTAMP NOT NULL,"
            "  end_ts TIMESTAMP,"
            "  status VARCHAR NOT NULL DEFAULT 'running'"
            ")"
        )
        conn.execute(
            "CREATE TABLE events ("
            "  event_id VARCHAR PRIMARY KEY,"
            "  event_type VARCHAR NOT NULL,"
            "  timestamp TIMESTAMP NOT NULL,"
            "  run_id VARCHAR NOT NULL,"
            "  payload JSON NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE TABLE quarantine ("
            "  symbol VARCHAR NOT NULL,"
            "  reason VARCHAR NOT NULL,"
            "  quarantined_date DATE NOT NULL,"
            "  cleared_date DATE,"
            "  severity VARCHAR NOT NULL DEFAULT 'QUARANTINE',"
            "  PRIMARY KEY (symbol, quarantined_date)"
            ")"
        )
        conn.close()
        return db_path

    def test_load_equity_curve_empty(self, seed: Path) -> None:
        db = DashboardDB(str(seed))
        rows = db.load_equity_curve()
        assert rows == []

    def test_load_equity_curve_populated(self, seed: Path) -> None:
        conn = duckdb.connect(str(seed))
        conn.execute(
            "INSERT INTO equity_curve VALUES ('2026-06-10', 100000.0, 50000.0, 'RISK_ON', 'PAPER')"
        )
        conn.execute(
            "INSERT INTO equity_curve VALUES ('2026-06-11', 101000.0, 49000.0, 'RISK_ON', 'PAPER')"
        )
        conn.close()
        db = DashboardDB(str(seed))
        rows = db.load_equity_curve()
        assert len(rows) == 2
        assert rows[-1]["equity"] == 101000.0

    def test_load_positions_empty(self, seed: Path) -> None:
        db = DashboardDB(str(seed))
        assert db.load_positions() == []

    def test_load_positions_populated(self, seed: Path) -> None:
        conn = duckdb.connect(str(seed))
        conn.execute(
            "INSERT INTO positions VALUES"
            " ('AAPL', 100.0, 150.0, 150.0, 155.0, 145.0, NULL, 15500.0, 500.0,"
            " '2026-06-01', 160.0, false)"
        )
        conn.close()
        db = DashboardDB(str(seed))
        rows = db.load_positions()
        assert len(rows) == 1
        assert rows[0]["symbol"] == "AAPL"

    def test_load_journals_empty(self, seed: Path) -> None:
        db = DashboardDB(str(seed))
        assert db.load_journals() == []

    def test_load_journals_populated(self, seed: Path) -> None:
        conn = duckdb.connect(str(seed))
        conn.execute("INSERT INTO journal_entries VALUES ('2026-06-11', 'Journal content')")
        conn.close()
        db = DashboardDB(str(seed))
        rows = db.load_journals()
        assert len(rows) == 1

    def test_load_reports_empty(self, seed: Path) -> None:
        db = DashboardDB(str(seed))
        assert db.load_reports() == []

    def test_load_reports_populated(self, seed: Path) -> None:
        conn = duckdb.connect(str(seed))
        conn.execute("INSERT INTO reports VALUES ('2026-06-11', 'weekly', 'Report content')")
        conn.close()
        db = DashboardDB(str(seed))
        rows = db.load_reports()
        assert len(rows) == 1

    def test_load_latest_run_empty(self, seed: Path) -> None:
        db = DashboardDB(str(seed))
        assert db.load_latest_run() is None

    def test_load_latest_run_populated(self, seed: Path) -> None:
        conn = duckdb.connect(str(seed))
        conn.execute(
            "INSERT INTO runs VALUES ('run-1', 'backtest', 'abc123', '2026-06-11 09:00:00', NULL, 'completed')"
        )
        conn.close()
        db = DashboardDB(str(seed))
        row = db.load_latest_run()
        assert row is not None
        assert row["run_type"] == "backtest"
        assert row["status"] == "completed"

    def test_load_quarantine_empty(self, seed: Path) -> None:
        db = DashboardDB(str(seed))
        assert db.load_quarantine() == []

    def test_load_quarantine_populated(self, seed: Path) -> None:
        conn = duckdb.connect(str(seed))
        conn.execute(
            "INSERT INTO quarantine VALUES ('AAPL', 'Stale data', '2026-06-11', NULL, 'QUARANTINE')"
        )
        conn.close()
        db = DashboardDB(str(seed))
        rows = db.load_quarantine()
        assert len(rows) == 1

    def test_load_quarantine_cleared_excluded(self, seed: Path) -> None:
        conn = duckdb.connect(str(seed))
        conn.execute(
            "INSERT INTO quarantine VALUES ('AAPL', 'Stale data', '2026-06-10', '2026-06-11', 'QUARANTINE')"
        )
        conn.close()
        db = DashboardDB(str(seed))
        assert db.load_quarantine() == []

    def test_load_staleness_events_empty(self, seed: Path) -> None:
        db = DashboardDB(str(seed))
        assert db.load_staleness_events() == []

    def test_load_staleness_events_populated(self, seed: Path) -> None:
        conn = duckdb.connect(str(seed))
        payload = json.dumps({"symbol": "AAPL", "hours_since_last": 48.0})
        conn.execute(
            "INSERT INTO events VALUES ('evt-1', 'staleness_halt_set', '2026-06-11 10:00:00', 'run-1', ?)",
            [payload],
        )
        conn.close()
        db = DashboardDB(str(seed))
        rows = db.load_staleness_events()
        assert len(rows) == 1

    def test_all_helpers_no_crash_on_missing_tables(self) -> None:
        db = DashboardDB(":memory:")
        assert db.load_equity_curve() == []
        assert db.load_positions() == []
        assert db.load_journals() == []
        assert db.load_reports() == []
        assert db.load_latest_run() is None
        assert db.load_all_runs() == []
        assert db.load_quarantine() == []
        assert db.load_staleness_events() == []
        db.close()

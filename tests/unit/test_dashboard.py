"""Smoke tests for dashboard helper functions."""

import json
from pathlib import Path

import duckdb
import pytest

from alpha_quant.app.dashboard import (
    _build_concepts_manifest,
    _load_equity_curve,
    _load_journals,
    _load_latest_run,
    _load_positions,
    _load_quarantine,
    _load_reports,
    _load_staleness_events,
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


class TestBuildConceptsManifest:
    def test_builds_from_md_files(self, tmp_path: Path) -> None:
        (tmp_path / "atr.md").write_text(
            "---\nid: atr\ntitle: ATR Explained\ndifficulty: beginner\n---\n\nContent"
        )
        (tmp_path / "risk.md").write_text(
            "---\nid: risk\ntitle: Risk Management\ndifficulty: intermediate\n---\n\nContent"
        )
        cards = _build_concepts_manifest(tmp_path)
        assert len(cards) == 2
        titles = {c["title"] for c in cards}
        assert "ATR Explained" in titles
        assert "Risk Management" in titles
        difficulties = {c["difficulty"] for c in cards}
        assert "beginner" in difficulties
        assert "intermediate" in difficulties

    def test_missing_frontmatter_falls_back(self, tmp_path: Path) -> None:
        (tmp_path / "test-card.md").write_text("No frontmatter here")
        cards = _build_concepts_manifest(tmp_path)
        assert len(cards) == 1
        assert cards[0]["id"] == "test-card"
        assert cards[0]["title"] == "Test Card"

    def test_empty_directory(self, tmp_path: Path) -> None:
        cards = _build_concepts_manifest(tmp_path)
        assert cards == []


class TestDashboardDBHelpers:
    @pytest.fixture
    def db(self) -> duckdb.DuckDBPyConnection:
        conn = duckdb.connect()
        conn.execute(
            "CREATE TABLE IF NOT EXISTS positions ("
            "  symbol VARCHAR PRIMARY KEY,"
            "  quantity DOUBLE NOT NULL,"
            "  entry_price DOUBLE,"
            "  avg_cost DOUBLE NOT NULL,"
            "  current_price DOUBLE,"
            "  stop_price DOUBLE,"
            "  trail_price DOUBLE,"
            "  market_value DOUBLE,"
            "  unrealized_pl DOUBLE,"
            "  realized_pl DOUBLE,"
            "  sector VARCHAR,"
            "  decision_id VARCHAR,"
            "  entry_date DATE,"
            "  high_since_entry DOUBLE,"
            "  partial_taken BOOLEAN"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS equity_curve ("
            "  equity_date DATE NOT NULL,"
            "  equity DOUBLE NOT NULL,"
            "  cash DOUBLE NOT NULL DEFAULT 0,"
            "  nav DOUBLE NOT NULL DEFAULT 0,"
            "  book VARCHAR NOT NULL DEFAULT 'PAPER',"
            "  PRIMARY KEY (equity_date, book)"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS journal_entries ("
            "  entry_date DATE PRIMARY KEY,"
            "  content TEXT NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS reports ("
            "  report_date DATE NOT NULL,"
            "  report_type VARCHAR NOT NULL,"
            "  content TEXT NOT NULL,"
            "  PRIMARY KEY (report_date, report_type)"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS runs ("
            "  run_id VARCHAR PRIMARY KEY,"
            "  run_type VARCHAR NOT NULL,"
            "  config_hash VARCHAR NOT NULL,"
            "  fixture_version VARCHAR,"
            "  start_ts TIMESTAMP NOT NULL,"
            "  end_ts TIMESTAMP,"
            "  status VARCHAR NOT NULL DEFAULT 'running',"
            "  manifest_hash VARCHAR"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS events ("
            "  event_id VARCHAR PRIMARY KEY,"
            "  event_type VARCHAR NOT NULL,"
            "  timestamp TIMESTAMP NOT NULL,"
            "  run_id VARCHAR NOT NULL,"
            "  payload JSON NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS quarantine ("
            "  symbol VARCHAR NOT NULL,"
            "  reason VARCHAR NOT NULL,"
            "  quarantined_date DATE NOT NULL,"
            "  cleared_date DATE,"
            "  severity VARCHAR NOT NULL DEFAULT 'QUARANTINE',"
            "  PRIMARY KEY (symbol, quarantined_date)"
            ")"
        )
        return conn

    def test_load_equity_curve_empty(self, db: duckdb.DuckDBPyConnection) -> None:
        df = _load_equity_curve(db)
        assert df.empty

    def test_load_equity_curve_populated(self, db: duckdb.DuckDBPyConnection) -> None:
        db.execute(
            "INSERT INTO equity_curve VALUES ('2026-06-10', 100000.0, 50000.0, 100000.0, 'PAPER')"
        )
        db.execute(
            "INSERT INTO equity_curve VALUES ('2026-06-11', 101000.0, 49000.0, 101000.0, 'PAPER')"
        )
        df = _load_equity_curve(db)
        assert len(df) == 2
        assert float(df.iloc[-1].equity) == 101000.0

    def test_load_positions_empty(self, db: duckdb.DuckDBPyConnection) -> None:
        df = _load_positions(db)
        assert df.empty

    def test_load_positions_populated(self, db: duckdb.DuckDBPyConnection) -> None:
        db.execute(
            "INSERT INTO positions (symbol, quantity, avg_cost, current_price, stop_price,"
            " market_value, unrealized_pl, entry_date, high_since_entry, partial_taken)"
            " VALUES ('AAPL', 100.0, 150.0, 155.0, 145.0, 15500.0, 500.0,"
            " '2026-06-01', 160.0, false)"
        )
        db.execute(
            "INSERT INTO positions (symbol, quantity, avg_cost, current_price, stop_price,"
            " market_value, unrealized_pl, entry_date, high_since_entry, partial_taken)"
            " VALUES ('MSFT', 50.0, 300.0, 310.0, 290.0, 15500.0, 500.0,"
            " '2026-06-05', 315.0, true)"
        )
        df = _load_positions(db)
        assert len(df) == 2
        assert set(df["symbol"].tolist()) == {"AAPL", "MSFT"}
        assert "entry_date" in df.columns
        assert "high_since_entry" in df.columns
        assert "partial_taken" in df.columns
        partials = df[df["partial_taken"] == True]  # noqa: E712
        assert len(partials) == 1
        assert partials.iloc[0]["symbol"] == "MSFT"

    def test_load_journals_empty(self, db: duckdb.DuckDBPyConnection) -> None:
        df = _load_journals(db)
        assert df.empty

    def test_load_journals_populated(self, db: duckdb.DuckDBPyConnection) -> None:
        db.execute(
            "INSERT INTO journal_entries VALUES ('2026-06-11', 'Journal content')"
        )
        df = _load_journals(db)
        assert len(df) == 1

    def test_load_reports_empty(self, db: duckdb.DuckDBPyConnection) -> None:
        df = _load_reports(db)
        assert df.empty

    def test_load_reports_populated(self, db: duckdb.DuckDBPyConnection) -> None:
        db.execute(
            "INSERT INTO reports VALUES ('2026-06-11', 'weekly', 'Report content')"
        )
        df = _load_reports(db)
        assert len(df) == 1

    def test_load_latest_run_empty(self, db: duckdb.DuckDBPyConnection) -> None:
        df = _load_latest_run(db)
        assert df.empty

    def test_load_latest_run_populated(self, db: duckdb.DuckDBPyConnection) -> None:
        db.execute(
            "INSERT INTO runs (run_id, run_type, config_hash, start_ts, status)"
            " VALUES ('run-1', 'backtest', 'abc123', '2026-06-11 09:00:00', 'completed')"
        )
        df = _load_latest_run(db)
        assert len(df) == 1
        assert df.iloc[0]["run_type"] == "backtest"
        assert df.iloc[0]["status"] == "completed"

    def test_load_quarantine_empty(self, db: duckdb.DuckDBPyConnection) -> None:
        df = _load_quarantine(db)
        assert df.empty

    def test_load_quarantine_populated(self, db: duckdb.DuckDBPyConnection) -> None:
        db.execute(
            "INSERT INTO quarantine (symbol, reason, quarantined_date, severity)"
            " VALUES ('AAPL', 'Stale data', '2026-06-11', 'QUARANTINE')"
        )
        df = _load_quarantine(db)
        assert len(df) == 1

    def test_load_quarantine_cleared_excluded(self, db: duckdb.DuckDBPyConnection) -> None:
        db.execute(
            "INSERT INTO quarantine (symbol, reason, quarantined_date, cleared_date, severity)"
            " VALUES ('AAPL', 'Stale data', '2026-06-10', '2026-06-11', 'QUARANTINE')"
        )
        df = _load_quarantine(db)
        assert df.empty

    def test_load_staleness_events_empty(self, db: duckdb.DuckDBPyConnection) -> None:
        df = _load_staleness_events(db)
        assert df.empty

    def test_load_staleness_events_populated(self, db: duckdb.DuckDBPyConnection) -> None:
        payload = json.dumps({"symbol": "AAPL", "hours_since_last": 48.0})
        db.execute(
            "INSERT INTO events (event_id, event_type, timestamp, run_id, payload)"
            " VALUES ('evt-1', 'staleness_halt_set', '2026-06-11 10:00:00', 'run-1', ?)",
            [payload],
        )
        df = _load_staleness_events(db)
        assert len(df) == 1

    def test_all_helpers_no_crash_on_missing_tables(self) -> None:
        conn = duckdb.connect()
        from pandas import DataFrame

        for loader in [
            _load_equity_curve,
            _load_positions,
            _load_journals,
            _load_reports,
            _load_latest_run,
            _load_quarantine,
            _load_staleness_events,
        ]:
            try:
                result = loader(conn)
                assert isinstance(result, DataFrame)
            except duckdb.CatalogException:
                pass
        conn.close()

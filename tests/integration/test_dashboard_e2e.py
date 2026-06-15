"""End-user integration tests for the Streamlit dashboard.

Uses streamlit.testing.v1.AppTest to run the dashboard headlessly.
Each test seeds a temporary state.db with realistic data and verifies
tab rendering via Streamlit's element query API.
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pytest
from streamlit.testing.v1 import AppTest

DASHBOARD_PATH = str(
    Path(__file__).resolve().parent.parent.parent / "alpha_quant" / "app" / "dashboard.py"
)


def _seed_state_db(db_path: Path, with_data: bool = True) -> None:
    conn = duckdb.connect(str(db_path))
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    conn.execute("INSERT INTO schema_version VALUES (1)")

    conn.execute(
        "CREATE TABLE IF NOT EXISTS equity_curve ("
        "  equity_date DATE NOT NULL,"
        "  equity DOUBLE NOT NULL,"
        "  cash DOUBLE NOT NULL DEFAULT 0,"
        "  nav DOUBLE NOT NULL DEFAULT 0,"
        "  regime VARCHAR NOT NULL DEFAULT 'CAUTION',"
        "  book VARCHAR NOT NULL DEFAULT 'PAPER',"
        "  PRIMARY KEY (equity_date, book)"
        ")"
    )
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
        "  partial_taken BOOLEAN NOT NULL DEFAULT FALSE"
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
    conn.execute(
        "CREATE TABLE IF NOT EXISTS decisions ("
        "  decision_id VARCHAR,"
        "  run_id VARCHAR,"
        "  symbol VARCHAR NOT NULL,"
        "  decision_date DATE NOT NULL,"
        "  action VARCHAR NOT NULL,"
        "  confidence DOUBLE NOT NULL,"
        "  reasons JSON,"
        "  candidate_json JSON,"
        "  risk_results JSON,"
        "  mechanism_results JSON,"
        "  PRIMARY KEY (symbol, decision_date)"
        ")"
    )

    if with_data:
        conn.execute(
            "INSERT INTO equity_curve VALUES"
            " ('2026-06-10', 100000.0, 80000.0, 100000.0, 'RISK_ON', 'PAPER'),"
            " ('2026-06-11', 101500.0, 79000.0, 101500.0, 'RISK_ON', 'PAPER'),"
            " ('2026-06-12', 102000.0, 78500.0, 102000.0, 'RISK_ON', 'PAPER')"
        )
        conn.execute(
            "INSERT INTO positions (symbol, quantity, entry_price, avg_cost,"
            " current_price, stop_price, market_value, unrealized_pl,"
            " entry_date, high_since_entry, partial_taken)"
            " VALUES ('AAPL', 100.0, 150.0, 150.0, 155.0, 145.0, 15500.0, 500.0,"
            " '2026-06-01', 160.0, FALSE),"
            " ('MSFT', 50.0, 300.0, 300.0, 310.0, 290.0, 15500.0, 500.0,"
            " '2026-06-05', 315.0, TRUE)"
        )
        conn.execute(
            "INSERT INTO journal_entries VALUES"
            " ('2026-06-11', '# Daily Journal\n\nNo trades today. Regime: RISK_ON.')"
        )
        conn.execute(
            "INSERT INTO reports VALUES"
            " ('2026-06-12', 'weekly', '# Weekly Report\n\nAll mechanisms healthy.'),"
            " ('2026-06-11', 'daily', '# Daily Report\n\nSPY up 0.5%')"
        )
        conn.execute(
            "INSERT INTO runs (run_id, run_type, config_hash, start_ts, status)"
            " VALUES ('run-001', 'daily', 'abc123',"
            " '2026-06-12 17:30:00', 'completed')"
        )
        conn.execute(
            "INSERT INTO events (event_id, event_type, timestamp, run_id, payload)"
            " VALUES ('evt-1', 'candidate_scored', '2026-06-12 17:30:01', 'run-001',"
            " '{\"symbol\": \"AAPL\", \"composite_score\": 0.75}'),"
            " ('evt-2', 'candidate_blocked', '2026-06-12 17:30:02', 'run-001',"
            " '{\"symbol\": \"TSLA\", \"gate\": \"risk\", \"reason\": \"Max positions reached\"}'),"
            " ('evt-3', 'stop_adjusted', '2026-06-12 17:30:03', 'run-001',"
            " '{\"symbol\": \"AAPL\", \"old_stop\": 140.0, \"new_stop\": 145.0}')"
        )
        conn.execute(
            "INSERT INTO decisions (decision_id, run_id, symbol, decision_date,"
            " action, confidence)"
            " VALUES ('dec-1', 'run-001', 'AAPL', '2026-06-12', 'enter', 0.75),"
            " ('dec-2', 'run-001', 'MSFT', '2026-06-12', 'enter', 0.70)"
        )

    conn.close()


@pytest.fixture
def seeded_db(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = data_dir / "state.db"
    _seed_state_db(db_path, with_data=True)
    return tmp_path


@pytest.fixture
def empty_db(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = data_dir / "state.db"
    _seed_state_db(db_path, with_data=False)
    return tmp_path


@pytest.fixture
def no_data_dir(tmp_path: Path) -> Path:
    return tmp_path


def _run_dashboard(work_dir: Path) -> AppTest:
    old_cwd = Path.cwd()
    os.chdir(work_dir)
    try:
        at = AppTest.from_file(DASHBOARD_PATH, default_timeout=10)
        at.run()
        return at
    finally:
        os.chdir(old_cwd)


class TestDashboardEmptyState:
    def test_no_data_dir_shows_warning(self, no_data_dir: Path) -> None:
        at = _run_dashboard(no_data_dir)
        warnings_text = [w.value for w in at.warning]
        assert any("Data directory not found" in w for w in warnings_text)

    def test_no_state_db_shows_warning(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        at = _run_dashboard(tmp_path)
        warnings_text = [w.value for w in at.warning]
        assert any("No state database found" in w for w in warnings_text)

    def test_empty_db_shows_no_equity_message(self, empty_db: Path) -> None:
        at = _run_dashboard(empty_db)
        info_text = [i.value for i in at.info]
        assert any("No equity data available" in i for i in info_text)


class TestDashboardSeeded:
    def test_beta_banner_present(self, seeded_db: Path) -> None:
        at = _run_dashboard(seeded_db)
        beta_warnings = [w.value for w in at.warning if "Beta Release" in w.value]
        assert len(beta_warnings) > 0

    def test_title_shown(self, seeded_db: Path) -> None:
        at = _run_dashboard(seeded_db)
        assert at.title[0].value == "Alpha Quant Dashboard"

    def test_home_tab_shows_system_status(self, seeded_db: Path) -> None:
        at = _run_dashboard(seeded_db)
        system_success = [s.value for s in at.success if "System Running" in s.value]
        assert len(system_success) > 0

    def test_home_tab_shows_equity_curve(self, seeded_db: Path) -> None:
        at = _run_dashboard(seeded_db)
        equity_metrics = [m for m in at.metric if m.label == "Equity"]
        assert len(equity_metrics) > 0
        assert equity_metrics[0].value == "$102,000.00"

    def test_home_tab_shows_last_run_info(self, seeded_db: Path) -> None:
        at = _run_dashboard(seeded_db)
        run_metrics = [m for m in at.metric if m.label == "Last Run Type"]
        assert len(run_metrics) > 0

    def test_home_tab_shows_portfolio_summary(self, seeded_db: Path) -> None:
        at = _run_dashboard(seeded_db)
        pos_metrics = [m for m in at.metric if m.label == "Open Positions"]
        assert len(pos_metrics) > 0
        assert pos_metrics[0].value == "2"

    def test_home_tab_shows_data_health(self, seeded_db: Path) -> None:
        at = _run_dashboard(seeded_db)
        health_messages = [s.value for s in at.success if "All data sources healthy" in s.value]
        assert len(health_messages) > 0

    def test_reports_tab_shows_reports(self, seeded_db: Path) -> None:
        at = _run_dashboard(seeded_db)
        at.tabs[2].run()
        assert len(at.selectbox) > 0

    def test_concepts_tab_lists_cards(self, seeded_db: Path) -> None:
        at = _run_dashboard(seeded_db)
        at.tabs[3].run()
        assert len(at.selectbox) > 0

    def test_journal_tab_shows_entries(self, seeded_db: Path) -> None:
        at = _run_dashboard(seeded_db)
        at.tabs[4].run()
        assert len(at.selectbox) > 0

    def test_decision_explorer_shows_info_on_empty_input(self, seeded_db: Path) -> None:
        at = _run_dashboard(seeded_db)
        at.tabs[5].run()
        info_messages = [i.value for i in at.info if "Enter a symbol" in i.value]
        assert len(info_messages) > 0

    def test_portfolio_tab_shows_positions_dataframe(self, seeded_db: Path) -> None:
        at = _run_dashboard(seeded_db)
        at.tabs[1].run()
        info_messages = [i.value for i in at.info if "No open positions" in i.value]
        assert len(info_messages) == 0

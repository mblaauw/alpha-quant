"""DuckDB state store operations.

CanonicalStore composite — inherits all per-sub-interface mixins
and provides shared DuckDB connection setup + schema initialization.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import structlog

from alpha_quant.application.store.admin_store import AdminStoreMixin
from alpha_quant.application.store.decision_store import DecisionStoreMixin
from alpha_quant.application.store.event_store import EventStoreMixin
from alpha_quant.application.store.journal_store import JournalStoreMixin
from alpha_quant.application.store.order_store import OrderStoreMixin
from alpha_quant.application.store.position_store import PositionStoreMixin
from alpha_quant.domain.models import IndicatorState
from alpha_quant.ports.store import Store

logger = structlog.get_logger()


class CanonicalStore(
    Store,
    DecisionStoreMixin,
    OrderStoreMixin,
    PositionStoreMixin,
    EventStoreMixin,
    JournalStoreMixin,
    AdminStoreMixin,
):
    SCHEMA_VERSION: int = 1

    def __init__(self, base_path: str | Path) -> None:
        self._base = Path(base_path)
        self._base.mkdir(parents=True, exist_ok=True)

        self._state_path = self._base / "state.db"
        self._state_conn = duckdb.connect(str(self._state_path))
        self._init_state_schema()

    def _init_state_schema(self) -> None:
        conn = self._state_conn
        conn.execute("CREATE TABLE IF NOT EXISTS schema_version (  version INTEGER NOT NULL)")
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        current_version = row[0] if row and row[0] else 0
        if current_version > 0 and current_version != self.SCHEMA_VERSION:
            logger.warning(
                "schema_version_mismatch",
                current=current_version,
                expected=self.SCHEMA_VERSION,
            )
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)",
            [self.SCHEMA_VERSION],
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
            "  position_json JSON,"
            "  order_json JSON,"
            "  risk_results JSON,"
            "  mechanism_results JSON,"
            "  PRIMARY KEY (symbol, decision_date)"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS orders ("
            "  order_id VARCHAR PRIMARY KEY,"
            "  symbol VARCHAR NOT NULL,"
            "  action VARCHAR NOT NULL,"
            "  quantity DOUBLE NOT NULL,"
            "  order_type VARCHAR NOT NULL,"
            "  limit_price DOUBLE,"
            "  status VARCHAR NOT NULL,"
            "  submitted_at TIMESTAMP,"
            "  fill_date TIMESTAMP,"
            "  filled_quantity DOUBLE,"
            "  avg_fill_price DOUBLE"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS fills ("
            "  fill_id VARCHAR PRIMARY KEY,"
            "  order_id VARCHAR NOT NULL,"
            "  symbol VARCHAR NOT NULL,"
            "  quantity DOUBLE NOT NULL,"
            "  price DOUBLE NOT NULL,"
            "  filled_at TIMESTAMP NOT NULL,"
            "  fee DOUBLE"
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
        conn.execute("ALTER TABLE positions ADD COLUMN IF NOT EXISTS entry_date DATE")
        conn.execute("ALTER TABLE positions ADD COLUMN IF NOT EXISTS high_since_entry DOUBLE")
        conn.execute("ALTER TABLE positions ADD COLUMN IF NOT EXISTS partial_taken BOOLEAN")
        conn.execute("UPDATE positions SET partial_taken = FALSE WHERE partial_taken IS NULL")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS equity_curve ("
            "  equity_date DATE NOT NULL,"
            "  equity DOUBLE NOT NULL,"
            "  cash DOUBLE NOT NULL DEFAULT 0,"
            "  regime VARCHAR NOT NULL DEFAULT 'CAUTION',"
            "  book VARCHAR NOT NULL DEFAULT 'PAPER',"
            "  PRIMARY KEY (equity_date, book)"
            ")"
        )
        conn.execute(
            "ALTER TABLE equity_curve ADD COLUMN IF NOT EXISTS regime VARCHAR DEFAULT 'CAUTION'"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_equity_curve_book "
            "ON equity_curve (book, equity_date DESC)"
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
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS concept_log ("
            "  log_id INTEGER PRIMARY KEY,"
            "  symbol VARCHAR,"
            "  concept VARCHAR NOT NULL,"
            "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
            "  meta JSON"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS catalog ("
            "  dataset VARCHAR NOT NULL,"
            "  version VARCHAR NOT NULL,"
            "  symbol VARCHAR NOT NULL,"
            "  coverage_start DATE,"
            "  coverage_end DATE,"
            "  row_count BIGINT,"
            "  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
            "  PRIMARY KEY (dataset, version, symbol)"
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
            "CREATE TABLE IF NOT EXISTS indicator_state ("
            "  symbol VARCHAR NOT NULL,"
            "  effective_date DATE NOT NULL,"
            "  data JSON,"
            "  PRIMARY KEY (symbol, effective_date)"
            ")"
        )
        conn.commit()

    def save_indicator_state(self, state: IndicatorState) -> None:
        import json

        cur = self._state_conn.execute(
            "INSERT OR REPLACE INTO indicator_state (symbol, effective_date, data) "
            "VALUES (?, ?, ?)",
            [state.symbol, str(state.date), json.dumps(state.model_dump(mode="json"))],
        )
        cur.close()

    def load_indicator_state(self, symbol: str, dt: date) -> IndicatorState | None:
        cur = self._state_conn.execute(
            "SELECT data FROM indicator_state WHERE symbol = ? AND effective_date = ?",
            [symbol, str(dt)],
        )
        row = cur.fetchone()
        cur.close()
        if row:
            return IndicatorState.model_validate(row[0])
        return None

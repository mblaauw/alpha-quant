"""FixtureStore — in-memory DuckDB for deterministic testing.

Stores state in an in-memory DuckDB database, reusing the same mixins
as CanonicalStore. This ensures fixture mode exercises the same code
paths as live mode (ADR-0029).
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Self

import duckdb

from alpha_quant.application.store.admin_store import AdminStoreMixin
from alpha_quant.application.store.decision_store import DecisionStoreMixin
from alpha_quant.application.store.event_store import EventStoreMixin
from alpha_quant.application.store.indicator_store import IndicatorStoreMixin
from alpha_quant.application.store.journal_store import JournalStoreMixin
from alpha_quant.application.store.order_store import OrderStoreMixin
from alpha_quant.application.store.position_store import PositionStoreMixin
from alpha_quant.ports.store import Store


class FixtureStore(
    Store,
    DecisionStoreMixin,
    OrderStoreMixin,
    PositionStoreMixin,
    EventStoreMixin,
    IndicatorStoreMixin,
    JournalStoreMixin,
    AdminStoreMixin,
):
    def __init__(self) -> None:
        self._state_conn = duckdb.connect(":memory:")
        self._init_schema()

    def _init_schema(self) -> None:
        conn = self._state_conn
        conn.execute(
            "CREATE TABLE IF NOT EXISTS decisions ("
            "  decision_id VARCHAR, run_id VARCHAR, symbol VARCHAR NOT NULL,"
            "  decision_date DATE NOT NULL, action VARCHAR NOT NULL,"
            "  confidence DOUBLE NOT NULL, reasons JSON, candidate_json JSON,"
            "  position_json JSON, order_json JSON, risk_results JSON,"
            "  mechanism_results JSON, PRIMARY KEY (symbol, decision_date)"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS orders ("
            "  order_id VARCHAR PRIMARY KEY, symbol VARCHAR NOT NULL,"
            "  action VARCHAR NOT NULL, quantity DOUBLE NOT NULL,"
            "  order_type VARCHAR NOT NULL, limit_price DOUBLE, status VARCHAR NOT NULL,"
            "  submitted_at TIMESTAMP, fill_date TIMESTAMP,"
            "  filled_quantity DOUBLE, avg_fill_price DOUBLE"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS fills ("
            "  fill_id VARCHAR PRIMARY KEY, order_id VARCHAR NOT NULL,"
            "  symbol VARCHAR NOT NULL, quantity DOUBLE NOT NULL,"
            "  price DOUBLE NOT NULL, filled_at TIMESTAMP NOT NULL, fee DOUBLE"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS positions ("
            "  symbol VARCHAR PRIMARY KEY, quantity DOUBLE NOT NULL,"
            "  entry_price DOUBLE, avg_cost DOUBLE NOT NULL, current_price DOUBLE,"
            "  stop_price DOUBLE, trail_price DOUBLE, market_value DOUBLE,"
            "  unrealized_pl DOUBLE, realized_pl DOUBLE, sector VARCHAR,"
            "  decision_id VARCHAR, entry_date DATE,"
            "  high_since_entry DOUBLE, partial_taken BOOLEAN NOT NULL DEFAULT FALSE"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS equity_curve ("
            "  equity_date DATE NOT NULL, equity DOUBLE NOT NULL,"
            "  cash DOUBLE NOT NULL DEFAULT 0, regime VARCHAR NOT NULL DEFAULT 'CAUTION',"
            "  book VARCHAR NOT NULL DEFAULT 'PAPER', PRIMARY KEY (equity_date, book)"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS events ("
            "  event_id VARCHAR PRIMARY KEY, event_type VARCHAR NOT NULL,"
            "  timestamp TIMESTAMP NOT NULL, run_id VARCHAR NOT NULL,"
            "  payload JSON NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS indicator_state ("
            "  symbol VARCHAR NOT NULL, effective_date DATE NOT NULL,"
            "  data JSON, PRIMARY KEY (symbol, effective_date)"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS quarantine ("
            "  symbol VARCHAR NOT NULL, reason VARCHAR NOT NULL,"
            "  quarantined_date DATE NOT NULL, cleared_date DATE,"
            "  severity VARCHAR NOT NULL DEFAULT 'QUARANTINE',"
            "  PRIMARY KEY (symbol, quarantined_date)"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS journal_entries ("
            "  entry_date DATE PRIMARY KEY, content TEXT NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS reports ("
            "  report_date DATE NOT NULL, report_type VARCHAR NOT NULL,"
            "  content TEXT NOT NULL, PRIMARY KEY (report_date, report_type)"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS runs ("
            "  run_id VARCHAR PRIMARY KEY, run_type VARCHAR NOT NULL,"
            "  config_hash VARCHAR NOT NULL, fixture_version VARCHAR,"
            "  start_ts TIMESTAMP NOT NULL, end_ts TIMESTAMP,"
            "  status VARCHAR NOT NULL DEFAULT 'running', manifest_hash VARCHAR"
            ")"
        )

    @contextmanager
    def transaction(self) -> Generator[Self]:
        yield self

    def close(self) -> None:
        self._state_conn.close()

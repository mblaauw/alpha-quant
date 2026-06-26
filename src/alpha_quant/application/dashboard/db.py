from __future__ import annotations

from collections.abc import Generator
from typing import Any

import duckdb
import structlog

logger = structlog.get_logger()

_EVT_CANDIDATE_BLOCKED = "candidate_blocked"
_EVT_CANDIDATE_SCORED = "candidate_scored"
_EVT_CANDIDATE_PROMOTED = "candidate_promoted"
_EVT_FILL_BOOKED = "fill_booked"
_EVT_STOP_ADJUSTED = "stop_adjusted"
_EVT_PARTIAL_TAKEN = "partial_taken"
_EVT_TIME_STOP_TRIGGERED = "time_stop_triggered"
_EVT_STALENESS_HALT_SET = "staleness_halt_set"
_EVT_CONSISTENCY_VIOLATION = "consistency_violation"

_SYMBOL_EVENT_TYPES = (
    _EVT_CANDIDATE_BLOCKED,
    _EVT_CANDIDATE_SCORED,
    _EVT_CANDIDATE_PROMOTED,
    _EVT_STOP_ADJUSTED,
    _EVT_PARTIAL_TAKEN,
    _EVT_TIME_STOP_TRIGGERED,
    _EVT_FILL_BOOKED,
)


def _rows(
    cursor: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None
) -> list[dict]:
    try:
        result = cursor.execute(sql, params) if params else cursor.execute(sql)  # noqa: SIM108
    except duckdb.CatalogException:
        logger.warning("table_not_found", query=sql[:80])
        return []
    except duckdb.Error as e:
        logger.warning("query_failed", query=sql[:80], error=str(e))
        return []
    cols = [desc[0] for desc in result.description]
    return [dict(zip(cols, row, strict=True)) for row in result.fetchall()]  # noqa: B905


def _row(
    cursor: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None
) -> dict | None:
    rows = _rows(cursor, sql, params)
    return rows[0] if rows else None


class DashboardDB:
    def __init__(self, db_path: str = "data/state.db") -> None:
        self._conn = duckdb.connect(db_path)

    def close(self) -> None:
        self._conn.close()

    def load_equity_curve(self, book: str = "PAPER") -> list[dict]:
        return _rows(
            self._conn,
            "SELECT equity_date, equity, cash FROM equity_curve"
            " WHERE book = ? ORDER BY equity_date",
            [book],
        )

    def load_positions(self) -> list[dict]:
        return _rows(
            self._conn,
            "SELECT symbol, quantity, entry_price, avg_cost, current_price,"
            " stop_price, trail_price, market_value, unrealized_pl,"
            " entry_date, high_since_entry, partial_taken"
            " FROM positions WHERE quantity > 0",
        )

    def load_journals(self) -> list[dict]:
        return _rows(
            self._conn,
            "SELECT entry_date FROM journal_entries ORDER BY entry_date DESC LIMIT 30",
        )

    def load_journal_content(self, entry_date: str) -> dict | None:
        return _row(
            self._conn,
            "SELECT content FROM journal_entries WHERE entry_date = ?",
            [entry_date],
        )

    def load_reports(self) -> list[dict]:
        return _rows(
            self._conn,
            "SELECT report_date, report_type FROM reports ORDER BY report_date DESC LIMIT 20",
        )

    def load_report_content(self, report_date: str, report_type: str) -> dict | None:
        return _row(
            self._conn,
            "SELECT content FROM reports WHERE report_date = ? AND report_type = ?",
            [report_date, report_type],
        )

    def load_latest_run(self) -> dict | None:
        return _row(
            self._conn,
            "SELECT run_id, run_type, start_ts, end_ts, status, config_hash"
            " FROM runs ORDER BY start_ts DESC LIMIT 1",
        )

    def load_all_runs(self) -> list[dict]:
        return _rows(
            self._conn,
            "SELECT run_id, run_type, start_ts, end_ts, status, config_hash"
            " FROM runs ORDER BY start_ts DESC LIMIT 10",
        )

    def load_run_events(self, run_id: str) -> list[dict]:
        return _rows(
            self._conn,
            "SELECT event_type, timestamp, payload FROM events WHERE run_id = ? ORDER BY timestamp",
            [run_id],
        )

    def load_quarantine(self) -> list[dict]:
        return _rows(
            self._conn,
            "SELECT symbol, reason, severity, quarantined_date"
            " FROM quarantine WHERE cleared_date IS NULL",
        )

    def load_staleness_events(self) -> list[dict]:
        return _rows(
            self._conn,
            f"SELECT payload FROM events WHERE event_type = '{_EVT_STALENESS_HALT_SET}'"
            " ORDER BY timestamp DESC LIMIT 5",
        )

    def load_consistency_violations(self) -> list[dict]:
        return _rows(
            self._conn,
            f"SELECT payload FROM events WHERE event_type = '{_EVT_CONSISTENCY_VIOLATION}'"
            " ORDER BY timestamp DESC LIMIT 5",
        )

    def load_symbol_options(self) -> list[str]:
        rows = _rows(
            self._conn,
            "SELECT DISTINCT symbol FROM decisions"
            " UNION"
            " SELECT DISTINCT symbol FROM positions WHERE quantity > 0"
            " ORDER BY symbol",
        )
        return [r["symbol"] for r in rows]

    def load_symbol_decisions(self, symbol: str) -> list[dict]:
        return _rows(
            self._conn,
            "SELECT decision_id, run_id, symbol, decision_date, action, confidence, reasons,"
            " candidate_json, risk_results, mechanism_results"
            " FROM decisions WHERE symbol = ? ORDER BY decision_date DESC LIMIT 20",
            [symbol],
        )

    def load_symbol_events(self, symbol: str) -> list[dict]:
        placeholders = ", ".join("?" for _ in _SYMBOL_EVENT_TYPES)
        return _rows(
            self._conn,
            f"SELECT event_type, timestamp, payload FROM events"
            f" WHERE event_type IN ({placeholders})"
            f" AND payload->>'symbol' = ?"
            f" ORDER BY timestamp DESC LIMIT 50",
            [*list(_SYMBOL_EVENT_TYPES), symbol],
        )


def get_db() -> Generator[DashboardDB]:
    db = DashboardDB()
    try:
        yield db
    finally:
        db.close()

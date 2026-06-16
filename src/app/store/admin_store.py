from __future__ import annotations

import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Self, override

import duckdb

from ports.store import AdminStore


class AdminStoreMixin(AdminStore):
    _state_conn: duckdb.DuckDBPyConnection
    _analytical: duckdb.DuckDBPyConnection
    _base: Path

    @contextmanager
    @override
    def transaction(self) -> Generator[Self]:
        self._state_conn.execute("BEGIN TRANSACTION")
        try:
            yield self  # type: ignore[misc]  # Generator covariance limitation — Self narrows to concrete
        except Exception:
            self._state_conn.execute("ROLLBACK")
            raise
        self._state_conn.execute("COMMIT")

    @override
    def add_quarantine(self, symbol: str, reason: str, severity: str = "QUARANTINE") -> None:
        self._state_conn.execute(
            "INSERT OR REPLACE INTO quarantine (symbol, reason, quarantined_date, severity)"
            " VALUES (?, ?, CURRENT_DATE, ?)",
            [symbol, reason, severity],
        )

    @override
    def list_quarantine(self, cleared: bool = False) -> list[dict[str, Any]]:
        if cleared:
            rows = self._state_conn.execute(
                "SELECT symbol, reason, quarantined_date, cleared_date, severity"
                " FROM quarantine WHERE cleared_date IS NOT NULL"
                " ORDER BY quarantined_date DESC"
            ).fetchall()
        else:
            rows = self._state_conn.execute(
                "SELECT symbol, reason, quarantined_date, cleared_date, severity"
                " FROM quarantine WHERE cleared_date IS NULL"
                " ORDER BY quarantined_date DESC"
            ).fetchall()
        return [
            {
                "symbol": r[0],
                "reason": r[1],
                "quarantined_date": str(r[2]),
                "cleared_date": str(r[3]) if r[3] else None,
                "severity": r[4],
            }
            for r in rows
        ]

    @override
    def clear_quarantine(self, symbol: str) -> None:
        self._state_conn.execute(
            "UPDATE quarantine SET cleared_date = CURRENT_DATE"
            " WHERE symbol = ? AND cleared_date IS NULL",
            [symbol],
        )

    @override
    def register_run(
        self,
        run_type: str,
        config_hash: str,
        fixture_version: str = "",
    ) -> str:
        run_id = uuid.uuid4().hex[:16]
        self._state_conn.execute(
            "INSERT INTO runs (run_id, run_type, config_hash, fixture_version, start_ts, status)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            [run_id, run_type, config_hash, fixture_version, datetime.now(UTC), "running"],
        )
        return run_id

    @override
    def complete_run(self, run_id: str, status: str = "completed", manifest_hash: str = "") -> None:
        self._state_conn.execute(
            "UPDATE runs SET end_ts = ?, status = ?, manifest_hash = ? WHERE run_id = ?",
            [datetime.now(UTC), status, manifest_hash, run_id],
        )

    @override
    def list_runs(self, since_date: date | None = None) -> list[dict[str, Any]]:
        if since_date is not None:
            rows = self._state_conn.execute(
                "SELECT run_id, run_type, config_hash, fixture_version,"
                " start_ts, end_ts, status, manifest_hash"
                " FROM runs WHERE start_ts >= ? ORDER BY start_ts DESC",
                [since_date],
            ).fetchall()
        else:
            rows = self._state_conn.execute(
                "SELECT run_id, run_type, config_hash, fixture_version,"
                " start_ts, end_ts, status, manifest_hash"
                " FROM runs ORDER BY start_ts DESC LIMIT 50"
            ).fetchall()
        return [
            {
                "run_id": r[0],
                "run_type": r[1],
                "config_hash": r[2],
                "fixture_version": r[3],
                "start_ts": str(r[4]),
                "end_ts": str(r[5]) if r[5] else None,
                "status": r[6],
                "manifest_hash": r[7],
            }
            for r in rows
        ]

    @override
    def close(self) -> None:
        self._analytical.close()
        self._state_conn.close()

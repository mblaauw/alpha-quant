from __future__ import annotations

from datetime import date
from typing import cast, override

import duckdb

from domain.journal import JournalEntry
from domain.reporting import ReportEntry, ReportType
from ports.store import JournalStore


class JournalStoreMixin(JournalStore):
    _state_conn: duckdb.DuckDBPyConnection

    @override
    def save_journal(self, entry: JournalEntry) -> None:
        self._state_conn.execute(
            "INSERT OR REPLACE INTO journal_entries (entry_date, content) VALUES (?, ?)",
            [entry.date.isoformat(), entry.content],
        )

    @override
    def load_journal(self, dt: date) -> JournalEntry | None:
        row = self._state_conn.execute(
            "SELECT content FROM journal_entries WHERE entry_date = ?",
            [dt.isoformat()],
        ).fetchone()
        if row is None:
            return None
        return JournalEntry(date=dt, content=row[0])

    @override
    def save_report(self, report: ReportEntry) -> None:
        self._state_conn.execute(
            "INSERT OR REPLACE INTO reports (report_date, report_type, content) VALUES (?, ?, ?)",
            [report.date.isoformat(), report.report_type, report.content],
        )

    @override
    def load_report(self, dt: date, report_type: str) -> ReportEntry | None:
        row = self._state_conn.execute(
            "SELECT content FROM reports WHERE report_date = ? AND report_type = ?",
            [dt.isoformat(), report_type],
        ).fetchone()
        if row is None:
            return None
        return ReportEntry(
            date=dt,
            report_type=cast("ReportType", report_type),
            content=row[0],
        )

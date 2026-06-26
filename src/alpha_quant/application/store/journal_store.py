from __future__ import annotations

from datetime import date
from typing import cast, override

import duckdb

from alpha_quant.application.store._crud import save_row
from alpha_quant.domain.journal import JournalEntry
from alpha_quant.domain.reporting import ReportEntry, ReportType
from alpha_quant.ports.store import JournalStore

JOURNAL_COLS = ["entry_date", "content"]
REPORT_COLS = ["report_date", "report_type", "content"]


class JournalStoreMixin(JournalStore):
    _state_conn: duckdb.DuckDBPyConnection

    @override
    def save_journal(self, entry: JournalEntry) -> None:
        save_row(
            self._state_conn,
            "journal_entries",
            JOURNAL_COLS,
            [
                entry.date.isoformat(),
                entry.content,
            ],
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
        save_row(
            self._state_conn,
            "reports",
            REPORT_COLS,
            [
                report.date.isoformat(),
                report.report_type,
                report.content,
            ],
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

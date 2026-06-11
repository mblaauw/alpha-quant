import sqlite3
from datetime import datetime
from pathlib import Path
from typing import override

import structlog
from pydantic import TypeAdapter

from alpha_quant.domain.events import DomainEvent
from alpha_quant.ports.event_sink import EventSink

_event_adapter = TypeAdapter(DomainEvent)

logger = structlog.get_logger()


class SqliteEventSink(EventSink):
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                run_id TEXT,
                event_type TEXT,
                ts TEXT,
                payload_json TEXT,
                source TEXT
            )
            """
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_events_run_id ON events(run_id)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts)")
        self._conn.commit()
        self._batch: list[DomainEvent] = []

    @override
    def emit(self, event: DomainEvent) -> None:
        self._batch.append(event)
        payload = event.model_dump_json()
        self._conn.execute(
            "INSERT INTO events (id, run_id, event_type, ts, payload_json, source)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                event.event_id,
                event.run_id,
                event.event_type,
                event.timestamp.isoformat(),
                payload,
                event.source,
            ),
        )
        logger.info("domain_event", event_type=event.event_type, run_id=event.run_id)

    def flush(self) -> None:
        self._conn.commit()
        self._batch = []

    @override
    def query(
        self,
        run_id: str | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[DomainEvent]:
        conditions: list[str] = []
        params: list[str] = []
        if run_id is not None:
            conditions.append("run_id = ?")
            params.append(run_id)
        if event_type is not None:
            conditions.append("event_type = ?")
            params.append(event_type)
        if since is not None:
            conditions.append("ts >= ?")
            params.append(since.isoformat())
        if until is not None:
            conditions.append("ts <= ?")
            params.append(until.isoformat())

        where = " AND ".join(conditions) if conditions else "1"
        rows = self._conn.execute(
            f"SELECT payload_json FROM events WHERE {where} ORDER BY ts",
            params,
        ).fetchall()
        return [_event_adapter.validate_json(row[0]) for row in rows]

    def close(self) -> None:
        self._conn.commit()
        self._conn.close()

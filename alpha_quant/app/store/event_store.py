from __future__ import annotations

import json
from datetime import datetime
from typing import Any, override

import duckdb

from alpha_quant.domain.events import DomainEvent
from alpha_quant.ports.store import EventStore


class EventStoreMixin(EventStore):
    _state_conn: duckdb.DuckDBPyConnection

    @override
    def save_event(self, event: DomainEvent) -> None:
        payload = event.model_dump(mode="json")
        self._state_conn.execute(
            "INSERT OR REPLACE INTO events"
            " (event_id, event_type, timestamp, run_id, payload)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                event.event_id,
                event.event_type,
                event.timestamp,
                event.run_id,
                json.dumps(payload),
            ],
        )

    @override
    def load_events(
        self,
        event_type: str | None = None,
        since: datetime | None = None,
    ) -> list[DomainEvent]:
        conditions: list[str] = []
        params: list[Any] = []
        if event_type is not None:
            conditions.append("event_type = ?")
            params.append(event_type)
        if since is not None:
            conditions.append("timestamp >= ?")
            params.append(since)

        where = " AND ".join(conditions) if conditions else "1=1"
        rows = self._state_conn.execute(
            f"SELECT payload FROM events WHERE {where} ORDER BY timestamp",
            params,
        ).fetchall()

        from alpha_quant.domain.events import DomainEvent as DomainEventType

        results: list[DomainEvent] = []
        for (payload_json,) in rows:
            payload = json.loads(payload_json)
            results.append(DomainEventType.model_validate(payload))
        return results

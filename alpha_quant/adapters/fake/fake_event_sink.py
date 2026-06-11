from datetime import datetime
from typing import override

from alpha_quant.domain.events import DomainEvent
from alpha_quant.ports.event_sink import EventSink


class FakeEventSink(EventSink):
    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    @override
    def emit(self, event: DomainEvent) -> None:
        self.events.append(event)

    @override
    def query(
        self,
        run_id: str | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[DomainEvent]:
        results: list[DomainEvent] = list(self.events)
        if run_id is not None:
            results = [e for e in results if getattr(e, "run_id", None) == run_id]
        if event_type is not None:
            results = [e for e in results if getattr(e, "event_type", None) == event_type]
        if since is not None:
            results = [e for e in results if getattr(e, "timestamp", datetime.min) >= since]
        if until is not None:
            results = [e for e in results if getattr(e, "timestamp", datetime.min) <= until]
        return results

"""Unit tests for EventLog."""

from datetime import UTC, datetime

from alpha_quant.domain.event_log import EventLog
from alpha_quant.domain.events import PipelineRunStarted


class _FakeStore:
    def __init__(self) -> None:
        self.events: list[object] = []

    def save_event(self, event: object) -> None:
        self.events.append(event)

    def load_events(self, event_type: str | None = None, since: datetime | None = None) -> list:
        return self.events

    def transaction(self) -> object:
        class _Txn:
            def __enter__(self) -> object:
                return self

            def __exit__(self, *args: object) -> None:
                pass

        return _Txn()


def _event(name: str = "test") -> PipelineRunStarted:
    return PipelineRunStarted(timestamp=datetime.now(UTC), run_id="test", source="test", mode="daily")  # noqa: E501


class TestEventLog:
    def test_emit_buffers_events(self) -> None:
        store = _FakeStore()
        log = EventLog(store, flush_interval_s=60.0, max_batch_size=100)
        log.emit(_event())
        assert log.buffer_size == 1
        assert len(store.events) == 0

    def test_flush_writes_to_store(self) -> None:
        store = _FakeStore()
        log = EventLog(store)
        log.emit(_event())
        log.flush()
        assert log.buffer_size == 0
        assert len(store.events) == 1

    def test_max_batch_triggers_auto_flush(self) -> None:
        store = _FakeStore()
        log = EventLog(store, flush_interval_s=60.0, max_batch_size=2)
        log.emit(_event())
        assert len(store.events) == 0
        log.emit(_event())
        assert len(store.events) == 2

    def test_subscribe_receives_events(self) -> None:
        store = _FakeStore()
        log = EventLog(store)
        received: list[str] = []
        log.subscribe(lambda e: received.append("called"))
        log.emit(_event())
        assert len(received) == 1

    def test_unsubscribe_stops_events(self) -> None:
        store = _FakeStore()
        log = EventLog(store)
        received: list[str] = []
        unsub = log.subscribe(lambda e: received.append("called"))
        unsub()
        log.emit(_event())
        assert len(received) == 0

    def test_query_flushes_and_returns_events(self) -> None:
        store = _FakeStore()
        log = EventLog(store)
        log.emit(_event("e1"))
        results = log.query()
        assert len(results) == 1

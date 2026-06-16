"""EventLog — in-memory event accumulator with batch flush and subscription."""

import threading
import time
from collections.abc import Callable
from datetime import datetime

from domain.events import DomainEvent
from ports.store import Store

_Subscription = Callable[[DomainEvent], None]


class EventLog:
    """In-memory event accumulator with periodic batch flush to store.

    Reduces write amplification by grouping events and flushing periodically
    instead of writing each event individually.
    """

    def __init__(
        self,
        store: Store,
        run_id: str = "",
        flush_interval_s: float = 10.0,
        max_batch_size: int = 100,
    ) -> None:
        self._store = store
        self._run_id = run_id
        self._flush_interval = flush_interval_s
        self._max_batch = max_batch_size
        self._buffer: list[DomainEvent] = []
        self._lock = threading.Lock()
        self._last_flush = time.monotonic()
        self._subscribers: list[_Subscription] = []

    def subscribe(self, callback: _Subscription) -> Callable[[], None]:
        """Register a callback invoked for every emitted event. Returns unsubscribe."""
        self._subscribers.append(callback)

        def _unsubscribe() -> None:
            if callback in self._subscribers:
                self._subscribers.remove(callback)

        return _unsubscribe

    def emit(self, event: DomainEvent) -> None:
        """Buffer an event. Flushes if batch size or interval is exceeded."""
        with self._lock:
            self._buffer.append(event)
            should_flush = (
                len(self._buffer) >= self._max_batch
                or (time.monotonic() - self._last_flush) >= self._flush_interval
            )
        for sub in self._subscribers:
            sub(event)
        if should_flush:
            self.flush()

    def flush(self) -> None:
        """Write all buffered events to the store in a single transaction."""
        with self._lock:
            batch = self._buffer
            self._buffer = []
            self._last_flush = time.monotonic()
        if not batch:
            return
        with self._store.transaction():
            for event in batch:
                self._store.save_event(event)

    def query(
        self,
        event_type: str | None = None,
        since: datetime | None = None,
    ) -> list[DomainEvent]:
        """Query both buffered and stored events."""
        self.flush()
        return self._store.load_events(event_type=event_type, since=since)

    @property
    def buffer_size(self) -> int:
        return len(self._buffer)

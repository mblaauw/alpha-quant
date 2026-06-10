from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class EventSink(Protocol):
    async def emit(self, event: str, context: dict | None = None) -> None: ...

    async def query(
        self, event_type: str | None = None, since: datetime | None = None
    ) -> list[dict]: ...

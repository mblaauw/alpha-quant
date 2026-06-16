from abc import ABC, abstractmethod
from datetime import datetime

from domain.events import DomainEvent


class EventSink(ABC):
    @abstractmethod
    def emit(self, event: DomainEvent) -> None: ...

    @abstractmethod
    def query(
        self,
        run_id: str | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[DomainEvent]: ...

from abc import ABC, abstractmethod
from datetime import datetime

from alpha_quant.domain.events import DomainEvent


class EventSink(ABC):
    @abstractmethod
    async def emit(self, event: DomainEvent) -> None: ...

    @abstractmethod
    async def query(
        self,
        run_id: str | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[DomainEvent]: ...

from abc import ABC, abstractmethod

from alpha_quant.domain.events import DomainEvent


class EventSink(ABC):
    @abstractmethod
    async def emit(self, event: DomainEvent) -> None: ...

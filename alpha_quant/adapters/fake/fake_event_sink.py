from alpha_quant.domain.events import DomainEvent
from alpha_quant.ports.event_sink import EventSink


class FakeEventSink(EventSink):
    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    async def emit(self, event: DomainEvent) -> None:
        self.events.append(event)

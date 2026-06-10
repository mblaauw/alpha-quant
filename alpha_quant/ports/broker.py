from abc import ABC, abstractmethod

from alpha_quant.domain.models import Fill, Order, Position


class Broker(ABC):
    @abstractmethod
    async def submit_order(self, order: Order) -> Order: ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool: ...

    @abstractmethod
    async def portfolio(
        self,
    ) -> dict: ...

    @abstractmethod
    async def positions(self) -> list[Position]: ...

    @abstractmethod
    async def fills(self, since: str | None = None) -> list[Fill]: ...

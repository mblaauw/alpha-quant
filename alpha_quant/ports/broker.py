from abc import ABC, abstractmethod

from alpha_quant.domain.models import Fill, Order, Position


class Broker(ABC):
    @abstractmethod
    def submit_order(self, order: Order) -> Order: ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool: ...

    @abstractmethod
    def portfolio(
        self,
    ) -> dict[str, object]: ...

    @abstractmethod
    def positions(self) -> list[Position]: ...

    @abstractmethod
    def fills(self, since: str | None = None) -> list[Fill]: ...

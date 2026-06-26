from abc import ABC, abstractmethod
from datetime import date, datetime


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime: ...

    @abstractmethod
    def today(self) -> date: ...

    @abstractmethod
    def market_date(self) -> date: ...

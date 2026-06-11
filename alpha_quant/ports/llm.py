from abc import ABC, abstractmethod


class LLM(ABC):
    @abstractmethod
    def explain(self, context: str) -> str: ...

    @abstractmethod
    def generate_card(self, symbol: str, data: str) -> str: ...

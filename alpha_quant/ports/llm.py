from abc import ABC, abstractmethod


class LLM(ABC):
    @abstractmethod
    async def explain(self, context: dict) -> str: ...

    @abstractmethod
    async def generate_card(self, symbol: str, data: dict) -> str: ...

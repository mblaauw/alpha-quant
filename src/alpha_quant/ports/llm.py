from abc import ABC, abstractmethod

from alpha_quant.domain._base import FrozenModel


class LLMConfig(FrozenModel):
    provider: str = "openrouter"
    model: str = "anthropic/claude-sonnet-4"
    base_url: str = ""
    api_key: str = ""
    timeout_s: int = 30


class LLM(ABC):
    @abstractmethod
    def explain(self, context: str) -> str: ...

    @abstractmethod
    def generate_card(self, symbol: str, data: str) -> str: ...

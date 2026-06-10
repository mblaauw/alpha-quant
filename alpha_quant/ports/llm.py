from typing import Protocol, runtime_checkable


@runtime_checkable
class LLM(Protocol):
    async def generate(self, prompt: str, **kwargs: object) -> str: ...

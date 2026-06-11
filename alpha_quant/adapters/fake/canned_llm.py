from typing import override

from alpha_quant.ports.llm import LLM


class CannedLLM(LLM):
    def __init__(self, response_template: str = "") -> None:
        self._template = response_template or "No explanation available."

    @override
    def explain(self, context: str) -> str:
        return self._template

    @override
    def generate_card(self, symbol: str, data: str) -> str:
        return f"## {symbol}\n\n{self._template}"

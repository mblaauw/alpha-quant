from string import Template

from alpha_quant.ports.llm import LLM


class CannedLLM(LLM):
    def __init__(
        self,
        template: str = "mock-response-for: $prompt",
        canned_responses: dict[str, str] | None = None,
    ) -> None:
        self._template = Template(template)
        self._canned = canned_responses or {}
        self.calls: list[dict] = []

    async def explain(self, context: dict) -> str:
        self.calls.append({"method": "explain", "context": context})
        prompt = str(context)
        if prompt in self._canned:
            return self._canned[prompt]
        return self._template.safe_substitute(prompt=prompt[:80])

    async def generate_card(self, symbol: str, data: dict) -> str:
        self.calls.append({"method": "generate_card", "symbol": symbol, "data": data})
        prompt = f"card-{symbol}"
        if prompt in self._canned:
            return self._canned[prompt]
        return self._template.safe_substitute(prompt=prompt)

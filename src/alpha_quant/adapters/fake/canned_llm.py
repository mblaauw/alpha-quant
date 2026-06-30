import json
from typing import override

from alpha_quant.ports.llm import LLM


class CannedLLM(LLM):
    def __init__(self, response_template: str = "") -> None:
        self._template = response_template or json.dumps(
            {
                "headline": "Deterministic canned recommendation",
                "summary": "CannedLLM output for testing.",
                "recommended_action": "hold",
                "confidence_label": "medium",
                "key_reasons": ["Canned test reason 1", "Canned test reason 2"],
                "main_risks": ["Canned test risk"],
                "what_changed_since_previous_run": [],
                "override_guidance": [],
            }
        )

    @override
    def explain(self, context: str) -> str:
        return self._template

    @override
    def generate_card(self, symbol: str, data: str) -> str:
        return json.dumps(
            {
                "symbol": symbol,
                "headline": f"Canned card for {symbol}",
                "summary": data,
            }
        )

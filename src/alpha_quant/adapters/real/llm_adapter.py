from __future__ import annotations

from typing import Any, override

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from alpha_quant.ports.llm import LLM, LLMConfig

logger = structlog.get_logger()

_FALLBACK_CARD = "## {symbol}\n\nConcept card unavailable."
_SYSTEM_EXPLAIN = (
    "You are a quantitative trading assistant. "
    "Explain the provided trading context clearly and concisely."
)
_SYSTEM_CARD = (
    "You are a financial education assistant. "
    "Generate a clear, beginner-friendly explanation of the given trading concept."
)


class OpenAILikeLLM(LLM):
    def __init__(self, config: LLMConfig, client: httpx.Client | None = None) -> None:
        self._provider = config.provider
        self._model = config.model
        self._base_url = (config.base_url or "https://openrouter.ai/api").rstrip("/")
        self._api_key = config.api_key
        self._timeout = config.timeout_s
        self._client = client

    def _masked_key(self) -> str:
        k = self._api_key
        if len(k) <= 8:
            return "***"
        return k[:4] + "..." + k[-4:]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def _chat_completion(self, system: str, user: str) -> str:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.3,
        }
        url = f"{self._base_url}/v1/chat/completions"
        if self._client is not None:
            response = self._client.post(url, headers=headers, json=body)
        else:
            with httpx.Client(timeout=httpx.Timeout(self._timeout)) as c:
                response = c.post(url, headers=headers, json=body)
        response.raise_for_status()
        data = response.json()
        return str(data["choices"][0]["message"]["content"])

    @override
    def explain(self, context: str) -> str:
        return self._chat_completion(_SYSTEM_EXPLAIN, context)

    @override
    def generate_card(self, symbol: str, data: str) -> str:
        try:
            result = self._chat_completion(_SYSTEM_CARD, f"{symbol}: {data}")
            return result
        except Exception:
            logger.exception(
                "LLM generate_card failed (provider=%s, symbol=%s, key=%s); using fallback",
                self._provider,
                symbol,
                self._masked_key(),
            )
            return _FALLBACK_CARD.format(symbol=symbol)

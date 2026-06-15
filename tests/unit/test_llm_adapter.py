"""Unit tests for LLM adapter (alpha_quant.adapters.real.llm_adapter)."""

import httpx

from alpha_quant.adapters.real.llm_adapter import OpenAILikeLLM
from alpha_quant.ports.llm import LLMConfig


def _config(**kwargs: str | int) -> LLMConfig:
    data: dict = {
        "provider": "test",
        "model": "test-model",
        "api_key": "sk-test-key-12345678",
        "timeout_s": 30,
    }
    data.update(kwargs)
    return LLMConfig(**data)


def _mock_client(json_body: dict, status: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=json_body)

    return httpx.Client(transport=httpx.MockTransport(handler))


class TestOpenAILikeLLM:
    def test_explain_returns_content(self) -> None:
        client = _mock_client({"choices": [{"message": {"content": "The market is trending up."}}]})
        llm = OpenAILikeLLM(_config(), client=client)
        result = llm.explain("context data")
        assert result == "The market is trending up."

    def test_generate_card_returns_content(self) -> None:
        client = _mock_client(
            {"choices": [{"message": {"content": "## AAPL\n\nApple is a tech company."}}]}
        )
        llm = OpenAILikeLLM(_config(), client=client)
        result = llm.generate_card("AAPL", "some data")
        assert "AAPL" in result
        assert "Apple" in result

    def test_explain_returns_fallback_on_http_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        llm = OpenAILikeLLM(_config(), client=client)
        result = llm.explain("context")
        assert "No explanation available" in result

    def test_generate_card_returns_fallback_on_http_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        llm = OpenAILikeLLM(_config(), client=client)
        result = llm.generate_card("AAPL", "data")
        assert "AAPL" in result

    def test_explain_fallback_on_malformed_response(self) -> None:
        client = _mock_client({"unexpected": "response"})
        llm = OpenAILikeLLM(_config(), client=client)
        result = llm.explain("context")
        assert "No explanation available" in result

    def test_sends_correct_request_body(self) -> None:
        import json

        sent: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            sent.append(json.loads(request.read()))
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        llm = OpenAILikeLLM(_config(model="my-model"), client=client)
        llm.explain("test context")
        assert len(sent) == 1
        assert sent[0]["model"] == "my-model"
        assert sent[0]["temperature"] == 0.3
        assert sent[0]["messages"][0]["role"] == "system"
        assert sent[0]["messages"][1]["role"] == "user"

    def test_sends_auth_header(self) -> None:
        headers: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            headers.update(dict(request.headers))
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        llm = OpenAILikeLLM(_config(api_key="sk-test-key"), client=client)
        llm.explain("test")
        assert headers.get("authorization") == "Bearer sk-test-key"

    def test_masked_key_shows_first_and_last_4(self) -> None:
        llm = OpenAILikeLLM(_config(api_key="sk-abcdefghijklmnop"))
        masked = llm._masked_key()
        assert masked == "sk-a...mnop"

    def test_masked_key_short_key(self) -> None:
        llm = OpenAILikeLLM(_config(api_key="short"))
        assert llm._masked_key() == "***"

    def test_custom_base_url(self) -> None:
        sent_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            sent_urls.append(str(request.url))
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        llm = OpenAILikeLLM(
            _config(base_url="https://api.openai.com"),
            client=client,
        )
        llm.explain("test")
        assert "https://api.openai.com/v1/chat/completions" in sent_urls[0]

    def test_default_base_url_is_openrouter(self) -> None:
        sent_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            sent_urls.append(str(request.url))
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        llm = OpenAILikeLLM(_config(base_url=""), client=client)
        llm.explain("test")
        assert "openrouter.ai" in sent_urls[0]

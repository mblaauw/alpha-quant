import httpx

from adapters.fake.fixture_fundamentals import FixtureFundamentals
from adapters.fake.fixture_insider_feed import FixtureInsiderFeed
from adapters.fake.fixture_market_data import FixtureMarketData
from adapters.fake.fixture_sentiment_feed import FixtureSentimentFeed
from adapters.fake.virtual_clock import VirtualClock
from adapters.real.base_connector import BaseConnector
from adapters.real.clock import SystemClock
from adapters.real.openinsider_connector import OpenInsiderConnector
from adapters.real.reddit_sentiment_connector import RedditSentimentConnector
from adapters.real.sec_connector import SECConnector
from app.config import AppConfig
from app.factory import (
    create_clock,
    create_fundamentals,
    create_insider_feed,
    create_market_data,
    create_sec_connector,
    create_sentiment_feed,
)


def _fixture_config() -> AppConfig:
    return AppConfig.model_validate(
        {
            "bootstrap": {"symbols": ["AAPL", "SPY"]},
            "data": {"mode": "fixture"},
            "universe": {},
            "portfolio": {},
            "paper": {},
            "risk": {},
            "shadow": {},
            "llm": {},
            "education": {},
            "connector": {},
            "eodhd": {},
            "alpaca": {},
            "dashboard": {},
        }
    )


def _live_config() -> AppConfig:
    return AppConfig.model_validate(
        {
            "bootstrap": {"symbols": ["AAPL", "SPY"]},
            "data": {"mode": "live"},
            "universe": {},
            "portfolio": {},
            "paper": {},
            "risk": {},
            "shadow": {},
            "llm": {},
            "education": {},
            "connector": {},
            "eodhd": {"api_key": "test_key"},
            "alpaca": {"api_key": "test_key", "secret_key": "test_secret"},
            "dashboard": {},
        }
    )


class TestCreateMarketData:
    def test_fixture_mode_returns_fixture_market_data(self) -> None:
        md = create_market_data(_fixture_config())
        assert isinstance(md, FixtureMarketData)


class TestCreateFundamentals:
    def test_fixture_mode_returns_fixture_fundamentals(self) -> None:
        fd = create_fundamentals(_fixture_config())
        assert isinstance(fd, FixtureFundamentals)


class TestCreateInsiderFeed:
    def test_fixture_mode_returns_fixture_insider_feed(self) -> None:
        ins = create_insider_feed(_fixture_config())
        assert isinstance(ins, FixtureInsiderFeed)

    def test_live_mode_returns_openinsider_connector(self) -> None:
        ins = create_insider_feed(_live_config())
        assert isinstance(ins, OpenInsiderConnector)
        ins.close()


class TestCreateSentimentFeed:
    def test_fixture_mode_returns_fixture_sentiment_feed(self) -> None:
        sf = create_sentiment_feed(_fixture_config())
        assert isinstance(sf, FixtureSentimentFeed)

    def test_live_mode_returns_reddit_sentiment_connector(self) -> None:
        sf = create_sentiment_feed(_live_config())
        assert isinstance(sf, RedditSentimentConnector)
        sf.close()


class TestCreateSECConnector:
    def test_always_returns_sec_connector(self) -> None:
        sec = create_sec_connector(_fixture_config())
        assert isinstance(sec, SECConnector)
        sec.close()


class TestCreateClock:
    def test_fixture_mode_returns_virtual_clock(self) -> None:
        clock = create_clock(_fixture_config())
        assert isinstance(clock, VirtualClock)

    def test_live_mode_returns_system_clock(self) -> None:
        clock = create_clock(_live_config())
        assert isinstance(clock, SystemClock)


class TestBaseConnectorCheckConnection:
    def test_returns_true_on_2xx(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        conn = BaseConnector(source_name="test", base_url="http://example.com")
        conn._client = client
        assert conn.check_connection() is True
        conn.close()

    def test_returns_true_on_4xx(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        conn = BaseConnector(source_name="test", base_url="http://example.com")
        conn._client = client
        assert conn.check_connection() is True
        conn.close()

    def test_returns_false_on_5xx(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        conn = BaseConnector(source_name="test", base_url="http://example.com")
        conn._client = client
        assert conn.check_connection() is False
        conn.close()

    def test_returns_false_on_request_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.RequestError("Connection refused")

        client = httpx.Client(transport=httpx.MockTransport(handler))
        conn = BaseConnector(source_name="test", base_url="http://example.com")
        conn._client = client
        assert conn.check_connection() is False
        conn.close()


class TestSECConnectorCheckConnection:
    def test_hits_sec_tickers_url(self) -> None:
        urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            urls.append(str(request.url))
            return httpx.Response(200)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        sec = SECConnector(user_agent="test", cache_path=":memory:", vault=None)
        sec._client = client
        try:
            assert sec.check_connection() is True
            assert any("company_tickers.json" in u for u in urls)
        finally:
            sec.close()

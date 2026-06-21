from datetime import date
from pathlib import Path

import httpx
import pytest

from adapters.fake.fixture_fundamentals import FixtureFundamentals
from adapters.fake.fixture_insider_feed import FixtureInsiderFeed
from adapters.fake.fixture_market_data import FixtureMarketData
from adapters.fake.fixture_sentiment_feed import FixtureSentimentFeed
from adapters.fake.lake_fixture import FixtureLakeGateway
from adapters.fake.virtual_clock import VirtualClock
from adapters.real.base_connector import BaseConnector
from adapters.real.clock import SystemClock
from adapters.real.lake_data import (
    LakeFundamentals,
    LakeInsiderFeed,
    LakeMarketData,
    LakeSentimentFeed,
)
from adapters.real.lake_inprocess import InProcessLakeGateway
from adapters.real.openinsider_connector import OpenInsiderConnector
from adapters.real.reddit_sentiment_connector import RedditSentimentConnector
from adapters.real.sec_connector import SECConnector
from app.config import AppConfig
from app.factory import (
    create_clock,
    create_fundamentals,
    create_insider_feed,
    create_lake_gateway,
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

    def test_lake_gateway_returns_lake_market_data(self) -> None:
        config = _fixture_config()
        clock = VirtualClock(date(2026, 1, 2))
        lake = FixtureLakeGateway(Path("fixtures/v1"))
        md = create_market_data(config, lake_gateway=lake, clock=clock)
        assert isinstance(md, LakeMarketData)


class TestCreateFundamentals:
    def test_fixture_mode_returns_fixture_fundamentals(self) -> None:
        fd = create_fundamentals(_fixture_config())
        assert isinstance(fd, FixtureFundamentals)

    def test_lake_gateway_returns_lake_fundamentals(self) -> None:
        config = _fixture_config()
        clock = VirtualClock(date(2026, 1, 2))
        lake = FixtureLakeGateway(Path("fixtures/v1"))
        fd = create_fundamentals(config, lake_gateway=lake, clock=clock)
        assert isinstance(fd, LakeFundamentals)


class TestCreateInsiderFeed:
    def test_fixture_mode_returns_fixture_insider_feed(self) -> None:
        ins = create_insider_feed(_fixture_config())
        assert isinstance(ins, FixtureInsiderFeed)

    def test_live_mode_returns_openinsider_connector(self) -> None:
        ins = create_insider_feed(_live_config())
        assert isinstance(ins, OpenInsiderConnector)
        ins.close()

    def test_lake_gateway_returns_lake_insider_feed(self) -> None:
        config = _fixture_config()
        clock = VirtualClock(date(2026, 1, 2))
        lake = FixtureLakeGateway(Path("fixtures/v1"))
        ins = create_insider_feed(config, lake_gateway=lake, clock=clock)
        assert isinstance(ins, LakeInsiderFeed)


class TestCreateSentimentFeed:
    def test_fixture_mode_returns_fixture_sentiment_feed(self) -> None:
        sf = create_sentiment_feed(_fixture_config())
        assert isinstance(sf, FixtureSentimentFeed)

    def test_live_mode_returns_reddit_sentiment_connector(self) -> None:
        sf = create_sentiment_feed(_live_config())
        assert isinstance(sf, RedditSentimentConnector)
        sf.close()

    def test_lake_gateway_returns_lake_sentiment_feed(self) -> None:
        config = _fixture_config()
        clock = VirtualClock(date(2026, 1, 2))
        lake = FixtureLakeGateway(Path("fixtures/v1"))
        sf = create_sentiment_feed(config, lake_gateway=lake, clock=clock)
        assert isinstance(sf, LakeSentimentFeed)


class TestCreateLakeGateway:
    def test_fixture_mode_returns_fixture_lake_gateway(self) -> None:
        config = _fixture_config()
        clock = VirtualClock(date(2026, 1, 2))
        lake = create_lake_gateway(config, clock)
        assert isinstance(lake, FixtureLakeGateway)

    def test_rest_mode_is_deferred(self) -> None:
        config = AppConfig.model_validate(
            {
                **_fixture_config().model_dump(mode="json"),
                "lake": {"mode": "rest"},
            }
        )
        clock = VirtualClock(date(2026, 1, 2))
        with pytest.raises(NotImplementedError, match="RestLakeGateway is deferred"):
            create_lake_gateway(config, clock)

    def test_in_process_mode_uses_configured_adapter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, str] = {}

        def fake_init(self: InProcessLakeGateway, config_path: str, price_mode: str) -> None:
            _ = self
            captured["config_path"] = config_path
            captured["price_mode"] = price_mode

        monkeypatch.setattr(InProcessLakeGateway, "__init__", fake_init)
        config = AppConfig.model_validate(
            {
                **_fixture_config().model_dump(mode="json"),
                "lake": {
                    "mode": "in_process",
                    "config_path": "../alpha-lake/config/test.toml",
                    "price_mode": "raw",
                },
            }
        )
        clock = VirtualClock(date(2026, 1, 2))
        lake = create_lake_gateway(config, clock)
        assert isinstance(lake, InProcessLakeGateway)
        assert captured == {"config_path": "../alpha-lake/config/test.toml", "price_mode": "raw"}


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

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from adapters.fake.canned_llm import CannedLLM
from adapters.fake.fake_broker import FakeBroker
from adapters.fake.fake_event_sink import FakeEventSink
from adapters.fake.fixture_store import FixtureStore
from adapters.fake.lake_fixture import FixtureLakeGateway
from adapters.fake.virtual_clock import VirtualClock
from adapters.real.alpaca_broker import AlpacaBroker
from adapters.real.clock import SystemClock
from adapters.real.event_sink import DuckDBEventSink
from adapters.real.lake_data import (
    LakeFundamentals,
    LakeInsiderFeed,
    LakeMarketData,
    LakeSentimentFeed,
)
from adapters.real.lake_inprocess import InProcessLakeGateway
from adapters.real.llm_adapter import OpenAILikeLLM
from app.config import AppConfig
from app.factory import (
    create_broker,
    create_clock,
    create_event_sink,
    create_fundamentals,
    create_insider_feed,
    create_lake_gateway,
    create_llm,
    create_market_data,
    create_sentiment_feed,
    create_store,
)
from app.store import CanonicalStore


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
            "alpaca": {"api_key": "test_key", "secret_key": "test_secret"},
            "dashboard": {},
        }
    )


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
        captured: dict[str, object] = {}

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
        assert captured == {
            "config_path": "../alpha-lake/config/test.toml",
            "price_mode": "raw",
        }


class TestCreateMarketData:
    def test_returns_lake_market_data(self) -> None:
        config = _fixture_config()
        clock = VirtualClock(date(2026, 1, 2))
        lake = FixtureLakeGateway(Path("fixtures/v1"))
        md = create_market_data(config, lake_gateway=lake, clock=clock)
        assert isinstance(md, LakeMarketData)


class TestCreateFundamentals:
    def test_returns_lake_fundamentals(self) -> None:
        config = _fixture_config()
        clock = VirtualClock(date(2026, 1, 2))
        lake = FixtureLakeGateway(Path("fixtures/v1"))
        fd = create_fundamentals(config, lake_gateway=lake, clock=clock)
        assert isinstance(fd, LakeFundamentals)


class TestCreateInsiderFeed:
    def test_returns_lake_insider_feed(self) -> None:
        config = _fixture_config()
        clock = VirtualClock(date(2026, 1, 2))
        lake = FixtureLakeGateway(Path("fixtures/v1"))
        ins = create_insider_feed(config, lake_gateway=lake, clock=clock)
        assert isinstance(ins, LakeInsiderFeed)


class TestCreateSentimentFeed:
    def test_returns_lake_sentiment_feed(self) -> None:
        config = _fixture_config()
        clock = VirtualClock(date(2026, 1, 2))
        lake = FixtureLakeGateway(Path("fixtures/v1"))
        sf = create_sentiment_feed(config, lake_gateway=lake, clock=clock)
        assert isinstance(sf, LakeSentimentFeed)


class TestCreateEventSink:
    def test_fixture_mode_returns_fake_event_sink(self) -> None:
        sink = create_event_sink(_fixture_config())
        assert isinstance(sink, FakeEventSink)

    def test_live_mode_returns_duckdb_event_sink(self) -> None:
        sink = create_event_sink(_live_config())
        assert isinstance(sink, DuckDBEventSink)
        sink.close()


class TestCreateStore:
    def test_fixture_mode_returns_fixture_store(self) -> None:
        store = create_store(_fixture_config())
        assert isinstance(store, FixtureStore)

    def test_live_mode_returns_canonical_store(self) -> None:
        store = create_store(_live_config())
        assert isinstance(store, CanonicalStore)


class TestCreateClock:
    def test_fixture_mode_returns_virtual_clock(self) -> None:
        clock = create_clock(_fixture_config())
        assert isinstance(clock, VirtualClock)

    def test_live_mode_returns_system_clock(self) -> None:
        clock = create_clock(_live_config())
        assert isinstance(clock, SystemClock)


class TestCreateLLM:
    def test_fixture_mode_returns_canned_llm(self) -> None:
        llm = create_llm(_fixture_config())
        assert isinstance(llm, CannedLLM)

    def test_live_mode_returns_openai_like_llm(self) -> None:
        llm = create_llm(_live_config())
        assert isinstance(llm, OpenAILikeLLM)


class TestCreateBroker:
    def test_fixture_mode_returns_fake_broker(self) -> None:
        broker = create_broker(_fixture_config())
        assert isinstance(broker, FakeBroker)

    def test_live_mode_returns_alpaca_broker(self) -> None:
        broker = create_broker(_live_config())
        assert isinstance(broker, AlpacaBroker)

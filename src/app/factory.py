from __future__ import annotations

from datetime import date
from pathlib import Path

from adapters.fake.canned_llm import CannedLLM
from adapters.fake.fake_event_sink import FakeEventSink
from adapters.fake.fixture_store import FixtureStore
from adapters.fake.lake_fixture import FixtureLakeGateway
from adapters.fake.virtual_clock import VirtualClock
from adapters.real.clock import SystemClock
from adapters.real.event_sink import DuckDBEventSink
from adapters.real.lake_data import (
    LakeFundamentals,
    LakeInsiderFeed,
    LakeMarketData,
    LakeSentimentFeed,
)
from adapters.real.lake_rest import RestLakeGateway
from adapters.real.llm_adapter import OpenAILikeLLM
from app.config import AppConfig
from app.store import CanonicalStore
from ports.clock import Clock
from ports.event_sink import EventSink
from ports.fundamentals import Fundamentals
from ports.insider_feed import InsiderFeed
from ports.lake import LakeGateway
from ports.llm import LLM
from ports.llm import LLMConfig as PortLLMConfig
from ports.market_data import MarketData
from ports.sentiment_feed import SentimentFeed
from ports.store import Store


def _lake_fixture_path(config: AppConfig) -> Path:
    return Path("fixtures") / config.lake.fixture_version


def create_lake_gateway(config: AppConfig, clock: Clock) -> LakeGateway:
    """Create the shared Alpha-Lake gateway for lake-backed data ports."""
    _ = clock
    if config.lake.mode == "fixture":
        lake = FixtureLakeGateway(_lake_fixture_path(config))
    elif config.lake.mode == "rest":
        import os

        lake = RestLakeGateway(
            base_url=config.lake.base_url,
            api_key=os.environ.get(config.lake.api_key_env, ""),
            price_mode=config.lake.price_mode,
        )
    else:
        msg = f"Unknown lake mode: {config.lake.mode}"
        raise ValueError(msg)

    lake.pin_snapshot(config.lake.snapshot_id or None)
    return lake


def create_market_data(
    config: AppConfig,
    lake_gateway: LakeGateway,
    clock: Clock,
) -> MarketData:
    return LakeMarketData(lake_gateway, clock, price_mode=config.lake.price_mode)


def create_fundamentals(
    config: AppConfig,
    lake_gateway: LakeGateway,
    clock: Clock,
) -> Fundamentals:
    return LakeFundamentals(lake_gateway, clock)


def create_insider_feed(
    config: AppConfig,
    lake_gateway: LakeGateway,
    clock: Clock,
) -> InsiderFeed:
    return LakeInsiderFeed(lake_gateway, clock)


def create_sentiment_feed(
    config: AppConfig,
    lake_gateway: LakeGateway,
    clock: Clock,
) -> SentimentFeed:
    return LakeSentimentFeed(lake_gateway, clock)


def create_event_sink(config: AppConfig) -> EventSink:
    if config.data.mode == "live":
        return DuckDBEventSink(db_path=Path("data") / "state.db")
    return FakeEventSink()


def create_store(config: AppConfig) -> Store:
    if config.data.mode == "live":
        return CanonicalStore(base_path=Path("data"))
    return FixtureStore()


def create_llm(config: AppConfig) -> LLM:
    if config.data.mode == "live":
        app_cfg = config.llm
        port_cfg = PortLLMConfig(
            provider=app_cfg.provider,
            model=app_cfg.model,
            base_url=app_cfg.base_url,
            api_key=app_cfg.api_key.get_secret_value(),
            timeout_s=app_cfg.timeout_s,
        )
        return OpenAILikeLLM(config=port_cfg)
    return CannedLLM()


def create_clock(config: AppConfig) -> Clock:
    if config.data.mode == "live":
        return SystemClock()
    return VirtualClock(date(2026, 1, 2))

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from adapters.fake.canned_llm import CannedLLM
from adapters.fake.fake_broker import FakeBroker
from adapters.fake.fake_event_sink import FakeEventSink
from adapters.fake.fixture_fundamentals import FixtureFundamentals
from adapters.fake.fixture_insider_feed import FixtureInsiderFeed
from adapters.fake.fixture_market_data import FixtureMarketData
from adapters.fake.fixture_sentiment_feed import FixtureSentimentFeed
from adapters.fake.fixture_store import FixtureStore
from adapters.fake.virtual_clock import VirtualClock
from adapters.real.alpaca_broker import AlpacaBroker
from adapters.real.alpaca_connector import AlpacaConnector
from adapters.real.clock import SystemClock
from adapters.real.eodhd_connector import EODHDConnector
from adapters.real.event_sink import DuckDBEventSink
from adapters.real.llm_adapter import OpenAILikeLLM
from adapters.real.openinsider_connector import OpenInsiderConnector
from adapters.real.reddit_sentiment_connector import RedditSentimentConnector
from adapters.real.sec_connector import SECConnector
from app.config import AppConfig
from app.store import CanonicalStore
from ports.broker import Broker
from ports.clock import Clock
from ports.event_sink import EventSink
from ports.fundamentals import Fundamentals
from ports.insider_feed import InsiderFeed
from ports.llm import LLM
from ports.llm import LLMConfig as PortLLMConfig
from ports.market_data import MarketData
from ports.sentiment_feed import SentimentFeed
from ports.store import Store

if TYPE_CHECKING:
    from app.vault import Vault


def _fixture_path(config: AppConfig) -> Path:
    return Path("fixtures") / config.data.fixture_version


def create_market_data(config: AppConfig, vault: Vault | None = None) -> MarketData:
    if config.data.mode == "live":
        return AlpacaConnector(
            api_key=config.alpaca.api_key.get_secret_value(),
            secret_key=config.alpaca.secret_key.get_secret_value(),
            base_url=config.alpaca.base_url,
            tokens_per_second=config.connector.tokens_per_second,
            max_burst=config.connector.max_burst,
            user_agent=config.connector.user_agent,
            vault=vault,
        )
    return FixtureMarketData(_fixture_path(config))


def create_fundamentals(config: AppConfig, vault: Vault | None = None) -> Fundamentals:
    if config.data.mode == "live":
        return EODHDConnector(
            api_token=config.eodhd.api_key.get_secret_value(),
            base_url=config.eodhd.base_url,
            tokens_per_second=config.connector.tokens_per_second,
            max_burst=config.connector.max_burst,
            user_agent=config.connector.user_agent,
            vault=vault,
        )
    return FixtureFundamentals(_fixture_path(config))


def create_insider_feed(config: AppConfig, vault: Vault | None = None) -> InsiderFeed:
    if config.data.mode == "live":
        return OpenInsiderConnector(
            user_agent=config.connector.user_agent,
            vault=vault,
        )
    return FixtureInsiderFeed(_fixture_path(config))


def create_sentiment_feed(config: AppConfig, vault: Vault | None = None) -> SentimentFeed:
    if config.data.mode == "live":
        return RedditSentimentConnector(
            symbols=config.bootstrap.symbols,
            user_agent=config.connector.user_agent,
            vault=vault,
        )
    return FixtureSentimentFeed(_fixture_path(config))


def create_sec_connector(
    config: AppConfig,
    vault: Vault | None = None,
    cache_path: str | None = None,
) -> SECConnector:
    return SECConnector(
        user_agent=config.connector.user_agent,
        cache_path=cache_path or "sec_cache.sqlite",
        vault=vault,
    )


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
        llm_cfg = config.llm
        return OpenAILikeLLM(
            config=PortLLMConfig(
                provider=llm_cfg.provider,
                model=llm_cfg.model,
                base_url=llm_cfg.base_url,
                api_key=llm_cfg.api_key.get_secret_value(),
                timeout_s=llm_cfg.timeout_s,
            )
        )
    return CannedLLM()


def create_broker(config: AppConfig) -> Broker:
    if config.data.mode == "live":
        return AlpacaBroker(
            api_key=config.alpaca.api_key.get_secret_value(),
            secret_key=config.alpaca.secret_key.get_secret_value(),
        )
    return FakeBroker()


def create_clock(config: AppConfig) -> Clock:
    if config.data.mode == "live":
        return SystemClock()
    return VirtualClock(start_date=date.today())

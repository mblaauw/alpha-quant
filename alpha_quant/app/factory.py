from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from alpha_quant.adapters.fake.canned_llm import CannedLLM
from alpha_quant.adapters.fake.fixture_fundamentals import FixtureFundamentals
from alpha_quant.adapters.fake.fixture_insider_feed import FixtureInsiderFeed
from alpha_quant.adapters.fake.fixture_market_data import FixtureMarketData
from alpha_quant.adapters.fake.fixture_sentiment_feed import FixtureSentimentFeed
from alpha_quant.adapters.fake.fixture_store import FixtureStore
from alpha_quant.adapters.fake.virtual_clock import VirtualClock
from alpha_quant.adapters.real.alpaca_connector import AlpacaConnector
from alpha_quant.adapters.real.clock import SystemClock
from alpha_quant.adapters.real.eodhd_connector import EODHDConnector
from alpha_quant.adapters.real.llm_adapter import OpenAILikeLLM
from alpha_quant.adapters.real.openinsider_connector import OpenInsiderConnector
from alpha_quant.adapters.real.reddit_sentiment_connector import RedditSentimentConnector
from alpha_quant.adapters.real.sec_connector import SECConnector
from alpha_quant.app.config import AppConfig
from alpha_quant.app.store import CanonicalStore
from alpha_quant.ports.clock import Clock
from alpha_quant.ports.fundamentals import Fundamentals
from alpha_quant.ports.insider_feed import InsiderFeed
from alpha_quant.ports.llm import LLM
from alpha_quant.ports.market_data import MarketData
from alpha_quant.ports.sentiment_feed import SentimentFeed
from alpha_quant.ports.store import Store

if TYPE_CHECKING:
    from alpha_quant.app.vault import Vault


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


def create_store(config: AppConfig) -> Store:
    if config.data.mode == "live":
        return CanonicalStore(base_path=Path("data"))
    return FixtureStore()


def create_llm(config: AppConfig) -> LLM:
    if config.data.mode == "live":
        return OpenAILikeLLM(config=config.llm)
    return CannedLLM()


def create_clock(config: AppConfig) -> Clock:
    if config.data.mode == "live":
        return SystemClock()
    return VirtualClock(start_date=date.today())

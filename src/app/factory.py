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
from adapters.real.clock import SystemClock
from adapters.real.eodhd_connector import EODHDConnector
from adapters.real.event_sink import DuckDBEventSink
from adapters.real.llm_adapter import OpenAILikeLLM
from adapters.real.openinsider_connector import OpenInsiderConnector
from adapters.real.reddit_sentiment_connector import RedditSentimentConnector
from adapters.real.sec_connector import SECConnector
from adapters.real.sec_fundamentals_connector import SECFundamentalsConnector
from app.config import AppConfig
from app.store import CanonicalStore
from domain.models import EarningsEntry, FundamentalsSnapshot
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


class CompositeFundamentals(Fundamentals):
    """Wraps multiple Fundamentals adapters, delegates primary calls.

    `.all` exposes all enabled adapters so ingest can save from every
    source tagged with the adapter's source_name.
    """

    _primary_name: str

    def __init__(self, adapters: list[Fundamentals], primary: str) -> None:
        self._adapters = adapters
        self._primary_name = primary

    @property
    def all(self) -> list[Fundamentals]:
        return self._adapters

    def _primary(self) -> Fundamentals:
        for a in self._adapters:
            if getattr(a, "_source_name", "") == self._primary_name:
                return a
        return self._adapters[0]

    def snapshot(self, symbol: str) -> FundamentalsSnapshot:
        snap = self._primary().snapshot(symbol)
        if snap is not None:
            snap = FundamentalsSnapshot(**snap.model_dump(), adapter=self._primary_name)
        return snap  # pyright: ignore[reportReturnType]

    def earnings_calendar(self, start: date, end: date) -> list[EarningsEntry]:
        entries = self._primary().earnings_calendar(start, end)
        return [EarningsEntry(**e.model_dump(), adapter=self._primary_name) for e in entries]


def _fixture_path(config: AppConfig) -> Path:
    return Path("fixtures") / config.data.fixture_version


def create_market_data(config: AppConfig, vault: Vault | None = None) -> MarketData:
    if config.data.mode == "live":
        from adapters.real.tiingo_connector import TiingoConnector

        return TiingoConnector(
            api_token=config.tiingo.api_key.get_secret_value(),
            base_url=config.tiingo.base_url,
            tokens_per_second=config.connector.tokens_per_second,
            max_burst=config.connector.max_burst,
            user_agent=config.connector.user_agent,
            vault=vault,
        )
    return FixtureMarketData(_fixture_path(config))


def _build_eodhd(config: AppConfig, vault: Vault | None = None) -> EODHDConnector:
    return EODHDConnector(
        api_token=config.eodhd.api_key.get_secret_value(),
        base_url=config.eodhd.base_url,
        tokens_per_second=config.connector.tokens_per_second,
        max_burst=config.connector.max_burst,
        user_agent=config.connector.user_agent,
        vault=vault,
    )


def _build_sec_edgar(config: AppConfig, vault: Vault | None = None) -> SECFundamentalsConnector:
    sec_cik = create_sec_connector(config, vault)
    return SECFundamentalsConnector(
        sec_cik=sec_cik,
        user_agent=config.connector.user_agent,
        tokens_per_second=10.0,
        max_burst=5.0,
        vault=vault,
    )


def create_fundamentals(config: AppConfig, vault: Vault | None = None) -> Fundamentals:
    if config.data.mode != "live":
        return FixtureFundamentals(_fixture_path(config))

    ac = config.adapters.fundamentals
    enabled_adapters: list[Fundamentals] = []

    for name, src in ac.sources.items():
        if not src.enabled:
            continue
        if name == "eodhd":
            enabled_adapters.append(_build_eodhd(config, vault))
        if name == "sec_edgar":
            enabled_adapters.append(_build_sec_edgar(config, vault))

    if not enabled_adapters:
        enabled_adapters.append(_build_eodhd(config, vault))

    if len(enabled_adapters) == 1:
        return enabled_adapters[0]

    primary = ac.primary or str(getattr(enabled_adapters[0], "_source_name", ""))
    return CompositeFundamentals(enabled_adapters, primary=primary)


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

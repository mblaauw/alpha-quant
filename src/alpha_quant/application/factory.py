from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from alpha_quant.adapters.fake.canned_llm import CannedLLM
from alpha_quant.adapters.fake.fake_event_sink import FakeEventSink
from alpha_quant.adapters.fake.fixture_store import FixtureStore
from alpha_quant.adapters.fake.virtual_clock import VirtualClock
from alpha_quant.adapters.postgres.unit_of_work import OperationalUnitOfWork
from alpha_quant.adapters.real.clock import SystemClock
from alpha_quant.adapters.real.event_sink import DuckDBEventSink
from alpha_quant.adapters.real.llm_adapter import OpenAILikeLLM

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker

from alpha_quant.application.config import AppConfig, FreshnessConfig
from alpha_quant.application.store import CanonicalStore
from alpha_quant.ports.alpha_lake import AlphaLakeReadPort
from alpha_quant.ports.clock import Clock
from alpha_quant.ports.event_sink import EventSink
from alpha_quant.ports.llm import LLM
from alpha_quant.ports.llm import LLMConfig as PortLLMConfig
from alpha_quant.ports.store import Store

DEFAULT_DATABASE_URL = (
    os.environ.get("DATABASE_URL")
    or "postgresql+psycopg://alpha_quant:alpha_quant_dev@localhost:5433/alpha_quant"
)


# -- Factory functions for the Alpha-Lake reader --


def create_alpha_lake_reader(config: AppConfig) -> AlphaLakeReadPort:
    from alpha_quant.adapters.fake.alpha_lake_http_fixture import (
        AlphaLakeHttpFixtureClient,
    )
    from alpha_quant.adapters.real.alpha_lake_rest import AlphaLakeRestClient

    if config.lake.mode in ("live", "rest"):
        import os

        client: AlphaLakeReadPort = AlphaLakeRestClient(
            base_url=config.lake.base_url,
            api_key=os.environ.get(config.lake.api_key_env, ""),
        )
        return client
    if config.lake.mode == "fixture":
        fixture_path = Path("fixtures") / config.lake.fixture_version
        return AlphaLakeHttpFixtureClient(fixture_path)
    msg = f"Unknown lake mode: {config.lake.mode}"
    raise ValueError(msg)


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


def create_freshness_service(
    lake: AlphaLakeReadPort,
    freshness_cfg: FreshnessConfig,
) -> object:
    from alpha_quant.application.query.freshness import FreshnessService

    return FreshnessService(
        lake=lake,
        sla_minutes=freshness_cfg.sla_minutes,
        critical_minutes=freshness_cfg.critical_minutes,
    )


def create_clock(config: AppConfig) -> Clock:
    if config.data.mode == "live":
        return SystemClock()
    return VirtualClock(date(2026, 1, 2))


# -- Factory functions for the PostgreSQL operational store --


def create_unit_of_work(database_url: str | None = None) -> OperationalUnitOfWork:
    """Create an OperationalUnitOfWork backed by PostgreSQL."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    url = database_url or DEFAULT_DATABASE_URL
    engine = create_engine(url, pool_size=5, max_overflow=10, pool_pre_ping=True)
    session_factory: sessionmaker[Session] = sessionmaker(bind=engine)
    return OperationalUnitOfWork(session_factory)


def run_migrations(database_url: str | None = None) -> None:
    """Run pending Alembic migrations."""
    from alembic import command
    from alembic.config import Config

    url = database_url or DEFAULT_DATABASE_URL
    ini_path = Path(__file__).resolve().parents[3] / "alembic.ini"
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(alembic_cfg, "head")


def seed_default_data(database_url: str | None = None) -> None:
    """Insert seed records (strategy, portfolio_book) if absent."""
    from uuid import uuid4

    from alpha_quant.adapters.postgres import create_engine, create_session
    from alpha_quant.adapters.postgres.tables import PortfolioBook, Strategy

    url = database_url or DEFAULT_DATABASE_URL
    engine = create_engine(url)
    session_factory = create_session(engine)

    with session_factory() as session:
        existing_strategies = session.query(Strategy).filter(Strategy.name == "default").first()
        if existing_strategies is None:
            session.add(
                Strategy(
                    strategy_id=str(uuid4()),
                    name="default",
                    created_at=__import__("datetime").datetime.now(
                        __import__("datetime").timezone.utc
                    ),
                )
            )
            session.commit()

        existing_book = session.query(PortfolioBook).filter(PortfolioBook.name == "default").first()
        if existing_book is None:
            from uuid import UUID as _UUID

            session.add(
                PortfolioBook(
                    book_id=str(_UUID("00000000-0000-0000-0000-000000000001")),
                    name="default",
                    kind="paper",
                    created_at=__import__("datetime").datetime.now(
                        __import__("datetime").timezone.utc
                    ),
                )
            )
            session.commit()

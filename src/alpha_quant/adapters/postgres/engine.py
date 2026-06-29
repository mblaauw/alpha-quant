from __future__ import annotations

import os

from sqlalchemy import create_engine as sa_create_engine
from sqlalchemy.orm import sessionmaker

from alpha_quant.adapters.postgres.tables import Base

DEFAULT_DATABASE_URL = (
    os.environ.get("DATABASE_URL")
    or "postgresql+psycopg://alpha_quant:alpha_quant_dev@localhost:5433/alpha_quant"
)


def create_engine(database_url: str = DEFAULT_DATABASE_URL, **kwargs: object):
    kwargs.setdefault("pool_size", 5)
    kwargs.setdefault("max_overflow", 10)
    kwargs.setdefault("pool_pre_ping", True)
    return sa_create_engine(database_url, **kwargs)


def create_session(engine=None):
    if engine is None:
        engine = create_engine()
    return sessionmaker(bind=engine)


def init_schema(engine):
    Base.metadata.create_all(engine)

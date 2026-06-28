from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from alpha_quant.adapters.postgres import create_engine

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg://alpha_quant:alpha_quant_dev@localhost:5433/alpha_quant"
)


def test_database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_TEST_DATABASE_URL)


def require_postgres_engine():
    engine = create_engine(test_database_url())
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        engine.dispose()
        pytest.skip(f"PostgreSQL test database unavailable: {exc}")
    return engine

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from alpha_quant.adapters.postgres.unit_of_work import OperationalUnitOfWork

DEFAULT_DATABASE_URL = "postgresql+psycopg://alpha_quant:alpha_quant_dev@localhost:5433/alpha_quant"
DEFAULT_BOOK_ID = UUID("00000000-0000-0000-0000-000000000001")


def with_uow(query_fn: Callable, database_url: str | None = None) -> Any:
    from alpha_quant.application.factory import create_unit_of_work

    uow = create_unit_of_work(database_url or DEFAULT_DATABASE_URL)
    with uow:
        return query_fn(uow)

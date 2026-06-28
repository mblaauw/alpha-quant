from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any
from uuid import UUID

DEFAULT_DATABASE_URL = (
    os.environ.get("DATABASE_URL")
    or "postgresql+psycopg://alpha_quant:alpha_quant_dev@localhost:5433/alpha_quant"
)
DEFAULT_BOOK_ID = UUID("00000000-0000-0000-0000-000000000001")


def with_uow(query_fn: Callable, database_url: str | None = None) -> Any:
    from alpha_quant.application.factory import create_unit_of_work

    uow = create_unit_of_work(database_url or DEFAULT_DATABASE_URL)
    with uow:
        return query_fn(uow)


def resolve_active_book_id() -> UUID:
    """Return the earliest-registered book as the active default."""
    try:
        from alpha_quant.application.factory import create_unit_of_work

        uow = create_unit_of_work()
        with uow:
            books = sorted(
                uow.store.list_books(),
                key=lambda b: b.created_at,
            )
            if books:
                return books[0].book_id
    except Exception:
        pass
    return DEFAULT_BOOK_ID

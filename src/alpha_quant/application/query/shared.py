from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from alpha_quant.adapters.postgres.engine import DEFAULT_DATABASE_URL

DEFAULT_BOOK_ID = UUID("00000000-0000-0000-0000-000000000001")
MOCK_BOOK_ID = UUID("00000000-0000-0000-0000-000000000002")


def _check_mock_mode():
    """Check ops.app_config for mock_mode flag using a throwaway UoW."""
    try:
        from alpha_quant.application.factory import create_unit_of_work

        uow = create_unit_of_work()
        with uow:
            val = uow.store.config_get("mock_mode")
            return val == "true"
    except Exception:
        return False


def with_uow(query_fn: Callable, database_url: str | None = None) -> Any:
    from alpha_quant.application.factory import create_unit_of_work

    uow = create_unit_of_work(database_url or DEFAULT_DATABASE_URL)
    with uow:
        return query_fn(uow)


def resolve_active_book_id() -> UUID:
    """Return active book — mock or earliest-registered book."""
    if _check_mock_mode():
        return MOCK_BOOK_ID
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

from __future__ import annotations

from alpha_quant.application.query.shared import with_uow, DEFAULT_BOOK_ID


class JournalService:
    def list_entries(
        self,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, object]:
        return {
            "items": [],
            "next_cursor": None,
        }

from __future__ import annotations


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

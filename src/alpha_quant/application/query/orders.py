from __future__ import annotations


class OrderService:
    def list_orders(
        self,
        book_id: str | None = None,
        status: str | None = None,
        symbol: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, object]:
        return {
            "items": [],
            "next_cursor": None,
        }

    def list_fills(
        self,
        book_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, object]:
        return {
            "items": [],
            "next_cursor": None,
        }

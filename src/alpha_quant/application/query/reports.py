from __future__ import annotations


class ReportService:
    def list_reports(
        self,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict[str, object]:
        return {
            "items": [],
            "next_cursor": None,
        }

    def get_report(self, report_date: str, report_type: str) -> dict[str, object] | None:
        return None

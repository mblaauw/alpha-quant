from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..db import DashboardDB, get_db

router = APIRouter(tags=["reports"])


@router.get("/api/v1/reports")
async def get_reports(
    db: DashboardDB = Depends(get_db),
) -> list[dict[str, object]]:
    return db.load_reports()


@router.get("/api/v1/reports/{report_date}/{report_type}")
async def get_report_content(
    report_date: str,
    report_type: str,
    db: DashboardDB = Depends(get_db),
) -> object:
    content = db.load_report_content(report_date, report_type)
    if content is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return content

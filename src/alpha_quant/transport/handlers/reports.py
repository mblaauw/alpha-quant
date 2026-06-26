from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from alpha_quant.application.query.reports import ReportService

router = APIRouter(tags=["reports"])


def _svc() -> ReportService:
    return ReportService()


@router.get("/reports")
async def list_reports(
    cursor: str | None = Query(None),
    limit: int = Query(20, le=100),
    svc: ReportService = Depends(_svc),
):
    return svc.list_reports(cursor=cursor, limit=limit)


@router.get("/reports/{report_date}/{report_type}")
async def get_report(
    report_date: str,
    report_type: str,
    svc: ReportService = Depends(_svc),
):
    return svc.get_report(report_date, report_type)

from __future__ import annotations

from fastapi import APIRouter, Query

from alpha_quant.application.query.reports import ReportService
from alpha_quant.transport.deps import svc_depends

router = APIRouter(tags=["reports"])


@router.get("/reports")
async def list_reports(
    cursor: str | None = Query(None),
    limit: int = Query(20, le=100),
    svc: ReportService = svc_depends(ReportService),
):
    return svc.list_reports(cursor=cursor, limit=limit)


@router.get("/reports/{report_date}/{report_type}")
async def get_report(
    report_date: str,
    report_type: str,
    svc: ReportService = svc_depends(ReportService),
):
    return svc.get_report(report_date, report_type)

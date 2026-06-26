from __future__ import annotations

from fastapi import APIRouter, Query

from alpha_quant.application.query.runs import RunService
from alpha_quant.transport.deps import svc_depends

router = APIRouter(tags=["runs"])


@router.get("/runs")
async def list_runs(
    book_id: str | None = Query(None),
    run_type: str | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(50, le=200),
    svc: RunService = svc_depends(RunService),
):
    return svc.list_runs(
        book_id=book_id,
        run_type=run_type,
        cursor=cursor,
        limit=limit,
    )


@router.get("/runs/{run_id}")
async def get_run(run_id: str, svc: RunService = svc_depends(RunService)):
    return svc.get_run(run_id)

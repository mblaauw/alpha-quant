from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from alpha_quant.application.query.runs import RunService

router = APIRouter(tags=["runs"])


def _svc() -> RunService:
    return RunService()


@router.get("/runs")
async def list_runs(
    book_id: str | None = Query(None),
    run_type: str | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(50, le=200),
    svc: RunService = Depends(_svc),
):
    return svc.list_runs(
        book_id=book_id,
        run_type=run_type,
        cursor=cursor,
        limit=limit,
    )


@router.get("/runs/{run_id}")
async def get_run(run_id: str, svc: RunService = Depends(_svc)):
    return svc.get_run(run_id)

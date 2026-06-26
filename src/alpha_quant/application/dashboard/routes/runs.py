from __future__ import annotations

from fastapi import APIRouter, Depends

from ..db import DashboardDB, get_db

router = APIRouter(tags=["runs"])


@router.get("/api/v1/runs/latest")
async def get_latest_run(
    db: DashboardDB = Depends(get_db),
) -> dict[str, object] | None:
    return db.load_latest_run()


@router.get("/api/v1/runs")
async def get_all_runs(
    db: DashboardDB = Depends(get_db),
) -> list[dict[str, object]]:
    return db.load_all_runs()

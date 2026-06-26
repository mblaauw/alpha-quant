from __future__ import annotations

from fastapi import APIRouter, Depends

from ..db import DashboardDB, get_db

router = APIRouter(tags=["events"])


@router.get("/api/v1/events/staleness")
async def get_staleness_events(
    db: DashboardDB = Depends(get_db),
) -> list[dict[str, object]]:
    return db.load_staleness_events()


@router.get("/api/v1/events/consistency-violations")
async def get_consistency_violations(
    db: DashboardDB = Depends(get_db),
) -> list[dict[str, object]]:
    return db.load_consistency_violations()

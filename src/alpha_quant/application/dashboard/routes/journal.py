from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..db import DashboardDB, get_db

router = APIRouter(tags=["journal"])


@router.get("/api/v1/journal")
async def get_journals(
    db: DashboardDB = Depends(get_db),
) -> list[dict[str, object]]:
    return db.load_journals()


@router.get("/api/v1/journal/{entry_date}")
async def get_journal_content(
    entry_date: str,
    db: DashboardDB = Depends(get_db),
) -> object:
    content = db.load_journal_content(entry_date)
    if content is None:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    return content

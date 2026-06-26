from __future__ import annotations

from fastapi import APIRouter, Query

from alpha_quant.application.query.journal import JournalService
from alpha_quant.transport.deps import svc_depends

router = APIRouter(tags=["journal"])


@router.get("/journal")
async def list_journal(
    cursor: str | None = Query(None),
    limit: int = Query(50, le=200),
    svc: JournalService = svc_depends(JournalService),
):
    return svc.list_entries(cursor=cursor, limit=limit)

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from alpha_quant.application.query.journal import JournalService

router = APIRouter(tags=["journal"])


def _svc() -> JournalService:
    return JournalService()


@router.get("/journal")
async def list_journal(
    cursor: str | None = Query(None),
    limit: int = Query(50, le=200),
    svc: JournalService = Depends(_svc),
):
    return svc.list_entries(cursor=cursor, limit=limit)

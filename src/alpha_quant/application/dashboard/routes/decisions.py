from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..db import DashboardDB, get_db

router = APIRouter(tags=["decisions"])


@router.get("/api/v1/decisions/symbols")
async def get_symbol_options(
    db: DashboardDB = Depends(get_db),
) -> list[str]:
    return db.load_symbol_options()


@router.get("/api/v1/decisions")
async def get_decisions(
    symbol: str = Query(...),
    db: DashboardDB = Depends(get_db),
) -> list[dict[str, object]]:
    decisions = db.load_symbol_decisions(symbol)
    events = db.load_symbol_events(symbol)
    timeline: list[dict[str, object]] = []
    for d in decisions:
        entry = dict(d)
        entry["_source"] = "decision"
        entry["_ts"] = d.get("decision_date", "")
        timeline.append(entry)
    for e in events:
        entry = dict(e)
        entry["_source"] = "event"
        entry["_ts"] = e.get("timestamp", "")
        timeline.append(entry)
    timeline.sort(key=lambda x: str(x.get("_ts", "")), reverse=True)
    return timeline

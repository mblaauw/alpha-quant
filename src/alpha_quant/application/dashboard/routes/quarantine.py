from __future__ import annotations

from fastapi import APIRouter, Depends

from alpha_quant.application.halt import is_halted, read_halt

from ..db import DashboardDB, get_db

router = APIRouter(tags=["quarantine"])


@router.get("/api/v1/quarantine")
async def get_quarantine(
    db: DashboardDB = Depends(get_db),
) -> list[dict[str, object]]:
    return db.load_quarantine()


@router.get("/api/v1/alerts")
async def get_alerts(
    db: DashboardDB = Depends(get_db),
) -> dict[str, object]:
    halted = is_halted()
    halt_reason: str | None = None
    if halted:
        info = read_halt()
        halt_reason = info.get("reason") if info else "unknown"

    positions = db.load_positions()
    near_stop: list[dict[str, object]] = []
    for p in positions:
        current = p.get("current_price")
        stop = p.get("stop_price")
        if current and stop and stop > 0:
            dist = (current - stop) / current * 100
            if dist < 5:
                near_stop.append(
                    {
                        "symbol": p.get("symbol"),
                        "dist_to_stop_pct": round(dist, 2),
                    }
                )

    return {
        "halted": halted,
        "halt_reason": halt_reason,
        "near_stop": near_stop,
        "quarantined": db.load_quarantine(),
        "staleness": db.load_staleness_events(),
        "violations": db.load_consistency_violations(),
    }

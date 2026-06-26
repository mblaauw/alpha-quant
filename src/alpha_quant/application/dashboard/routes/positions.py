from __future__ import annotations

from fastapi import APIRouter, Depends

from ..db import DashboardDB, get_db

router = APIRouter(tags=["positions"])


@router.get("/api/v1/positions")
async def get_positions(
    db: DashboardDB = Depends(get_db),
) -> list[dict[str, object]]:
    positions = db.load_positions()
    result: list[dict[str, object]] = []
    for p in positions:
        entry = dict(p)
        current = entry.get("current_price")
        stop = entry.get("stop_price")
        qty = entry.get("quantity", 0) or 0
        if current and stop and stop > 0:
            entry["dist_to_stop_pct"] = round((current - stop) / current * 100, 2)
            entry["risk_at_stop_dollars"] = round((current - stop) * qty, 2)
        else:
            entry["dist_to_stop_pct"] = None
            entry["risk_at_stop_dollars"] = 0.0
        result.append(entry)
    return result


@router.get("/api/v1/portfolio/risk")
async def get_portfolio_risk(
    db: DashboardDB = Depends(get_db),
) -> dict[str, object]:
    positions = db.load_positions()
    near_stop_count = 0
    total_risk_at_stop = 0.0
    for p in positions:
        current = p.get("current_price")
        stop = p.get("stop_price")
        qty = p.get("quantity", 0) or 0
        if current and stop and stop > 0:
            dist = (current - stop) / current * 100
            if dist < 5:
                near_stop_count += 1
            total_risk_at_stop += (current - stop) * qty
    return {
        "near_stop_count": near_stop_count,
        "total_risk_at_stop": round(total_risk_at_stop, 2),
        "open_positions": len(positions),
    }

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..db import DashboardDB, get_db

router = APIRouter(tags=["equity"])


@router.get("/api/v1/equity-curve")
async def get_equity_curve(
    db: DashboardDB = Depends(get_db),
) -> list[dict[str, object]]:
    return db.load_equity_curve()


@router.get("/api/v1/portfolio/summary")
async def get_portfolio_summary(
    db: DashboardDB = Depends(get_db),
) -> dict[str, object]:
    positions = db.load_positions()
    curve = db.load_equity_curve()
    open_positions = len(positions)
    total_market_value = sum(p.get("market_value", 0) or 0 for p in positions)
    total_unrealized_pl = sum(p.get("unrealized_pl", 0) or 0 for p in positions)
    latest_equity = curve[-1]["equity"] if curve else 0
    exposure_pct = (
        (total_market_value / latest_equity * 100) if latest_equity > 0 and len(curve) > 0 else 0
    )
    total_return_pct = 0.0
    if len(curve) >= 2:
        first_equity = curve[0]["equity"]
        last_equity = curve[-1]["equity"]
        if first_equity > 0:
            total_return_pct = (last_equity / first_equity - 1) * 100
    return {
        "open_positions": open_positions,
        "total_market_value": round(total_market_value, 2),
        "total_unrealized_pl": round(total_unrealized_pl, 2),
        "exposure_pct": round(exposure_pct, 2),
        "total_return_pct": round(total_return_pct, 2),
    }

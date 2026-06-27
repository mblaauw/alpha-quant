"""Console read API — operational read models for Alpha-Quant Desk.

All routes return cohesive JSON responses for the static SPA.
No route performs direct state mutation.
"""

from __future__ import annotations

import os
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from alpha_quant.application.config import AppConfig, FreshnessConfig, load_config
from alpha_quant.application.factory import (
    create_alpha_lake_reader,
    create_freshness_service,
)
from alpha_quant.application.query.command_center import CommandCenterService
from alpha_quant.application.query.decisions import DecisionService
from alpha_quant.application.query.freshness import FreshnessService
from alpha_quant.application.query.journal import JournalService
from alpha_quant.application.query.orders import OrderService
from alpha_quant.application.query.portfolio import PortfolioService
from alpha_quant.application.query.risk import RiskService
from alpha_quant.application.query.runs import RunService
from alpha_quant.application.query.system import SystemService
from alpha_quant.transport.deps import svc_depends

router = APIRouter(prefix="/v1/console", tags=["console"])


def _freshness_service() -> FreshnessService:  # noqa: B008
    cfg_path = os.environ.get("ALPHA_QUANT_CONFIG")
    if cfg_path:
        config = load_config(cfg_path)
    else:
        config = AppConfig(
            data={"mode": "fixture"},
            risk={
                "stop_atr_mult": 2.0,
                "trail_after_r": 1.0,
                "partial_take_at_r": 2.0,
                "time_stop_days": 30,
            },
            llm={"provider": "openrouter", "model": "anthropic/claude-sonnet-4"},
            lake={
                "mode": "rest",
                "base_url": os.environ.get("ALPHA_QUANT_LAKE__BASE_URL", "http://localhost:8000"),
            },
            freshness=FreshnessConfig(),
        )
    lake = create_alpha_lake_reader(config)
    return create_freshness_service(lake, config.freshness)  # type: ignore[return-value]


@router.get("/context")
async def get_context(svc: SystemService = svc_depends(SystemService)):
    return svc.context()


@router.get("/desk")
async def get_desk(
    svc: CommandCenterService = svc_depends(CommandCenterService),
    freshness: FreshnessService = Depends(_freshness_service),
):
    result = svc.summary()
    result["freshness_summary"] = freshness.summary([])
    return result


@router.get("/portfolio")
async def get_portfolio(svc: PortfolioService = svc_depends(PortfolioService)):
    return svc.summary()


@router.get("/positions")
async def list_positions(
    book_id: str | None = Query(None),
    svc: PortfolioService = svc_depends(PortfolioService),
    freshness: FreshnessService = Depends(_freshness_service),
):
    items = svc.list_positions(book_id=book_id)
    symbols = [p.get("symbol", "") for p in items if p.get("symbol")]
    freshness_map = {f["symbol"]: f for f in freshness.for_symbols(symbols)}
    for item in items:
        sym = item.get("symbol", "")
        item["freshness"] = freshness_map.get(sym)
    return {"items": items}


@router.get("/positions/{position_id}")
async def get_position(
    position_id: str,
    svc: PortfolioService = svc_depends(PortfolioService),
    freshness: FreshnessService = Depends(_freshness_service),
):
    result = svc.get_position(position_id)
    if result and result.get("symbol"):
        result["freshness"] = freshness.for_symbol(result["symbol"])
    return result


@router.get("/decisions")
async def list_decisions(
    book_id: str | None = Query(None),
    cursor: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    sort: str = Query("date", max_length=20),
    symbol: str | None = Query(None, max_length=10),
    run_id: str | None = Query(None, max_length=100),
    svc: DecisionService = svc_depends(DecisionService),
    freshness: FreshnessService = Depends(_freshness_service),
):
    result = svc.list_decisions(
        book_id=book_id, cursor=cursor, limit=limit, sort=sort, symbol=symbol, run_id=run_id
    )
    items = result.get("items", [])
    symbols = [d.get("symbol", "") for d in items if d.get("symbol")]
    freshness_map = {f["symbol"]: f for f in freshness.for_symbols(symbols)}
    for item in items:
        sym = item.get("symbol", "")
        f = freshness_map.get(sym)
        item["freshness"] = f
        if f and f.get("stale") and item.get("decision") in ("enter", "eligible", None):
            item["decision"] = "blocked"
            item["reason"] = f"Stale market data — {f['age_minutes']}m old"
    return result


@router.get("/decisions/{decision_id}")
async def get_decision(
    decision_id: str,
    svc: DecisionService = svc_depends(DecisionService),
):
    return svc.get_decision(decision_id)


@router.get("/orders")
async def list_orders(
    book_id: str | None = Query(None),
    status: str | None = Query(None, max_length=20),
    symbol: str | None = Query(None, max_length=10),
    cursor: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    svc: OrderService = svc_depends(OrderService),
):
    return svc.list_orders(
        book_id=book_id, status=status, symbol=symbol, cursor=cursor, limit=limit
    )


@router.get("/risk")
async def get_risk(
    book_id: str | None = Query(None),
    svc: RiskService = svc_depends(RiskService),
):
    return svc.summary(book_id=book_id)


@router.get("/runs")
async def list_runs(
    book_id: str | None = Query(None),
    run_type: str | None = Query(None, max_length=20),
    cursor: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    svc: RunService = svc_depends(RunService),
):
    return svc.list_runs(book_id=book_id, run_type=run_type, cursor=cursor, limit=limit)


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    svc: RunService = svc_depends(RunService),
):
    return svc.get_run(run_id)


@router.get("/journal")
async def list_journal(
    cursor: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    svc: JournalService = svc_depends(JournalService),
):
    return svc.list_entries(cursor=cursor, limit=limit)


@router.get("/system")
async def get_system(svc: SystemService = svc_depends(SystemService)):
    return svc.full_status()


@router.get("/freshness")
async def get_freshness(svc: FreshnessService = Depends(_freshness_service)):
    return svc.summary([])


# -- Advice Workflow endpoints --


@router.get("/advice/today")
async def get_today_advice(
    book_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    from alpha_quant.application.query.scorecards import get_today_advice as _get_today

    bid = UUID(book_id) if book_id else None
    return {"items": _get_today(book_id=bid, limit=limit)}


@router.get("/scorecards")
async def list_scorecards(
    run_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    from alpha_quant.application.query.scorecards import list_scorecards as _list

    return {"items": _list(run_id=run_id, limit=limit)}


@router.get("/scorecards/{scorecard_id}")
async def get_scorecard(scorecard_id: str):
    from fastapi import HTTPException

    from alpha_quant.application.query.scorecards import get_scorecard as _get

    sc = _get(scorecard_id)
    if sc is None:
        raise HTTPException(404, "Scorecard not found")
    return {
        "scorecard_id": sc.scorecard_id,
        "symbol": sc.symbol,
        "recommendation": sc.recommendation.value if sc.recommendation else "",
        "confidence": sc.confidence,
        "total_score": sc.total_score,
        "data_quality": sc.data_quality.value if sc.data_quality else "",
        "as_of": str(sc.as_of) if sc.as_of else None,
        "components": [
            {
                "name": c.name,
                "category": c.category,
                "score": c.score,
                "state": c.state.value,
                "weight": c.weight,
                "passed": c.passed,
                "reason": c.reason,
            }
            for c in sc.components
        ],
    }


@router.get("/symbols/{symbol}/scorecard")
async def get_symbol_scorecard(
    symbol: str,
    book_id: str | None = Query(None),
):
    from alpha_quant.application.query.scorecards import get_position_advice

    bid = UUID(book_id) if book_id else None
    items = get_position_advice(symbol, book_id=bid, limit=5)
    return {"items": items}


@router.get("/positions/{symbol}/advice")
async def get_position_advice(
    symbol: str,
    book_id: str | None = Query(None),
):
    from alpha_quant.application.query.scorecards import get_position_advice as _get_advice

    bid = UUID(book_id) if book_id else None
    items = _get_advice(symbol, book_id=bid, limit=5)
    return {"items": items}


@router.get("/risk-methods")
async def list_risk_methods():
    from alpha_quant.application.factory import create_unit_of_work

    uow = create_unit_of_work()
    with uow:
        return {"items": uow.store.list_risk_methods()}


@router.get("/lake-symbols")
async def list_lake_symbols(active_only: bool = Query(True)):
    from alpha_quant.application.config import load_config
    from alpha_quant.application.factory import create_alpha_lake_reader

    cfg_path = os.environ.get("ALPHA_QUANT_CONFIG")
    config = load_config(cfg_path) if cfg_path else None
    if config is None:
        return {"items": []}
    lake = create_alpha_lake_reader(config)
    try:
        symbols = lake.list_symbols(active_only=active_only)
        return {
            "items": [
                {"symbol": s.symbol, "added_at": s.added_at, "active": s.active} for s in symbols
            ]
        }
    finally:
        lake.close()

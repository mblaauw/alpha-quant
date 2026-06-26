"""Console read API — operational read models for Alpha-Quant Desk.

All routes return cohesive JSON responses for the static SPA.
No route performs direct state mutation.
"""

from __future__ import annotations

import os

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
            bootstrap={"symbols": ["SPY"], "history_years": 1},
            data={"mode": "fixture"},
            portfolio={"max_positions": 8, "max_gross_exposure": 0.8, "risk_per_trade_pct": 0.01},
            paper={"starting_equity": 100_000},
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
            dashboard={"host": "localhost", "port": 8501},
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

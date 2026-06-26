"""Console read API — operational read models for Alpha-Quant Desk.

All routes return cohesive JSON responses for the static SPA.
No route performs direct state mutation.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from alpha_quant.application.query.command_center import CommandCenterService
from alpha_quant.application.query.decisions import DecisionService
from alpha_quant.application.query.journal import JournalService
from alpha_quant.application.query.orders import OrderService
from alpha_quant.application.query.portfolio import PortfolioService
from alpha_quant.application.query.risk import RiskService
from alpha_quant.application.query.runs import RunService
from alpha_quant.application.query.system import SystemService
from alpha_quant.transport.deps import svc_depends

router = APIRouter(prefix="/v1/console", tags=["console"])


@router.get("/context")
async def get_context(svc: SystemService = svc_depends(SystemService)):
    return svc.context()


@router.get("/desk")
async def get_desk(svc: CommandCenterService = svc_depends(CommandCenterService)):
    return svc.summary()


@router.get("/portfolio")
async def get_portfolio(svc: PortfolioService = svc_depends(PortfolioService)):
    return svc.summary()


@router.get("/positions")
async def list_positions(
    book_id: str | None = Query(None),
    svc: PortfolioService = svc_depends(PortfolioService),
):
    return {"items": svc.list_positions(book_id=book_id)}


@router.get("/positions/{position_id}")
async def get_position(
    position_id: str,
    svc: PortfolioService = svc_depends(PortfolioService),
):
    return svc.get_position(position_id)


@router.get("/decisions")
async def list_decisions(
    book_id: str | None = Query(None),
    cursor: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    sort: str = Query("date", max_length=20),
    symbol: str | None = Query(None, max_length=10),
    run_id: str | None = Query(None, max_length=100),
    svc: DecisionService = svc_depends(DecisionService),
):
    return svc.list_decisions(
        book_id=book_id, cursor=cursor, limit=limit, sort=sort, symbol=symbol, run_id=run_id
    )


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

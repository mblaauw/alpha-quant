from __future__ import annotations

from fastapi import APIRouter

from .handlers import (
    command_center,
    decisions,
    halts,
    journal,
    orders,
    portfolio,
    reports,
    risk,
    runs,
    system,
)

router = APIRouter(tags=["dashboard"])

router.include_router(command_center.router)
router.include_router(decisions.router)
router.include_router(portfolio.router)
router.include_router(orders.router)
router.include_router(risk.router)
router.include_router(runs.router)
router.include_router(journal.router)
router.include_router(reports.router)
router.include_router(system.router)
router.include_router(halts.router)

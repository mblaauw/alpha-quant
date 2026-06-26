from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from alpha_quant.application.dashboard.routes.concepts import router as concepts_router
from alpha_quant.application.dashboard.routes.decisions import router as decisions_router
from alpha_quant.application.dashboard.routes.equity import router as equity_router
from alpha_quant.application.dashboard.routes.events import router as events_router
from alpha_quant.application.dashboard.routes.journal import router as journal_router
from alpha_quant.application.dashboard.routes.positions import router as positions_router
from alpha_quant.application.dashboard.routes.quarantine import router as quarantine_router
from alpha_quant.application.dashboard.routes.reports import router as reports_router
from alpha_quant.application.dashboard.routes.runs import router as runs_router
from alpha_quant.application.dashboard.routes.status import router as status_router

logger = structlog.get_logger()

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent.parent / "concepts"
DB_PATH = "data/state.db"


def _render_template(name: str) -> str:
    """Render a Jinja2 template with no context (no Jinja2 template syntax in page)."""
    path = TEMPLATES_DIR / name
    return path.read_text()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_path = DB_PATH
    logger.info("dashboard_startup", db_path=DB_PATH)
    yield
    logger.info("dashboard_shutdown")


app = FastAPI(title="Alpha Quant Dashboard", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

app.include_router(concepts_router)
app.include_router(decisions_router)
app.include_router(equity_router)
app.include_router(events_router)
app.include_router(journal_router)
app.include_router(positions_router)
app.include_router(quarantine_router)
app.include_router(reports_router)
app.include_router(runs_router)
app.include_router(status_router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
@app.get("/dashboard/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard() -> HTMLResponse:
    return HTMLResponse(_render_template("dashboard.html"))

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from alpha_quant.application.query.system import SystemService
from alpha_quant.transport.dashboard import router as dashboard_router
from alpha_quant.transport.health import router as health_router

logger = structlog.get_logger()

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("transport_startup")
    yield
    logger.info("transport_shutdown")


app = FastAPI(title="Alpha Quant", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Idempotency-Key", "X-Expected-Version", "X-CSRF-Token"],
)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

app.include_router(health_router)
app.include_router(dashboard_router, prefix="/v1/dashboard")


@app.get("/", include_in_schema=False)
async def index():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return {"status": "no-ui"}
    return FileResponse(str(index_path))

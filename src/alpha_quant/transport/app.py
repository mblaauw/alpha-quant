from __future__ import annotations

from contextlib import asynccontextmanager
from os import environ
from pathlib import Path

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from alpha_quant.transport.commands import router as commands_router
from alpha_quant.transport.dashboard import router as dashboard_router
from alpha_quant.transport.health import router as health_router

logger = structlog.get_logger()

STATIC_DIR = Path(__file__).resolve().parent / "static"
AQ_AUTH_MODE = environ.get("AQ_AUTH_MODE", "dev")
AQ_API_KEY = environ.get("AQ_API_KEY", "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("transport_startup", auth_mode=AQ_AUTH_MODE)
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


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if AQ_AUTH_MODE == "dev":
        return await call_next(request)

    if request.method == "POST" and request.url.path.startswith("/v1/commands"):
        api_key = request.headers.get("X-API-Key", "")
        if api_key != AQ_API_KEY:
            return JSONResponse({"error": "unauthorized"}, status_code=401)

    return await call_next(request)


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

app.include_router(health_router)
app.include_router(dashboard_router, prefix="/v1/dashboard")
app.include_router(commands_router)


@app.get("/", include_in_schema=False)
async def index():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return {"status": "no-ui"}
    return FileResponse(str(index_path))

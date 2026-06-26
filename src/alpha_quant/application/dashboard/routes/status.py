from __future__ import annotations

import os

from fastapi import APIRouter

router = APIRouter(tags=["status"])


@router.get("/api/v1/status")
async def get_status() -> dict[str, object]:
    halt_path = os.path.join("data", ".HALT")
    halted = os.path.exists(halt_path)
    reason: str | None = None
    if halted:
        try:
            with open(halt_path) as f:
                reason = f.readline().strip()
        except Exception:
            reason = "unknown"
    return {
        "halted": halted,
        "reason": reason,
        "status": "error" if halted else "ok",
    }

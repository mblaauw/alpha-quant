from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

HALT_PATH = Path("data") / ".HALT"


def halt_file_path() -> Path:
    return HALT_PATH


def is_halted() -> bool:
    return HALT_PATH.exists()


def read_halt() -> dict[str, str] | None:
    if not HALT_PATH.exists():
        return None
    try:
        raw = HALT_PATH.read_text()
        return dict(json.loads(raw))
    except Exception:
        return {"reason": "unknown", "timestamp": ""}


def write_halt(reason: str, run_id: str = "") -> None:
    HALT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, str] = {
        "reason": reason,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if run_id:
        payload["run_id"] = run_id
    HALT_PATH.write_text(json.dumps(payload, indent=2) + "\n")


def clear_halt() -> bool:
    if not HALT_PATH.exists():
        return False
    HALT_PATH.unlink()
    return True

"""Pipeline halt detection and control.

The system writes a ``.HALT`` sentinel file to prevent further pipeline
runs after a critical failure (staleness halt, max drawdown, data corruption).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

HALT_PATH = Path("data") / ".HALT"


def halt_file_path() -> Path:
    """Return the path to the halt sentinel file."""
    return HALT_PATH


def is_halted() -> bool:
    """Return True if a halt sentinel file exists."""
    return HALT_PATH.exists()


def read_halt() -> dict[str, str] | None:
    """Read halt metadata from the sentinel file.

    Returns:
        Dict with keys ``reason``, ``timestamp``, and optionally ``run_id``,
        or ``None`` if no halt is active.
    """
    if not HALT_PATH.exists():
        return None
    try:
        raw = HALT_PATH.read_text()
        return dict(json.loads(raw))
    except Exception:
        return {"reason": "unknown", "timestamp": ""}


def write_halt(reason: str, run_id: str = "") -> None:
    """Write a halt sentinel file with the given reason.

    Args:
        reason: Short description of why the pipeline halted.
        run_id: Optional run ID for traceability.
    """
    HALT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, str] = {
        "reason": reason,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if run_id:
        payload["run_id"] = run_id
    HALT_PATH.write_text(json.dumps(payload, indent=2) + "\n")


def clear_halt() -> bool:
    """Remove the halt sentinel file, if present.

    Returns:
        True if a file was removed, False if none existed.
    """
    if not HALT_PATH.exists():
        return False
    HALT_PATH.unlink()
    return True

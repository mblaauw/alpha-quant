"""Posture model — ready/elevated/halt state machine.

WS9 of the real risk engine epic (#612).
"""

from __future__ import annotations

from typing import Any


def derive_posture(
    events: list[dict[str, Any]],
    halted: bool = False,
    halt_details: str | None = None,
) -> dict[str, Any]:
    """Derive overall risk posture from events and halt state.

    halt > elevated > ready.
    Returns {state: str, text: str}.
    """
    if halted:
        return {
            "state": "halt",
            "text": halt_details
            or "Halted — all decision runs and execution are blocked pending review.",  # noqa: E501
        }

    critical = any(e.get("severity") == "crit" for e in events)
    warnings = any(e.get("severity") == "warn" for e in events)

    if critical:
        drivers = [e["title"] for e in events if e.get("severity") == "crit"]
        text = "Critical: " + "; ".join(drivers[:2]) + ". Immediate review required."
        return {"state": "elevated", "text": text}

    if warnings:
        drivers = [e["title"] for e in events if e.get("severity") == "warn"]
        text = "Caution: " + "; ".join(drivers[:2]) + ". Monitor before adding risk."
        return {"state": "elevated", "text": text}

    return {
        "state": "ready",
        "text": "Risk posture is ready; all limits within policy thresholds.",
    }

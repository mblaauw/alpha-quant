"""Composite scoring for trade candidates."""

from __future__ import annotations


def compute_composite(scores: dict[str, float]) -> float:
    technical = scores.get("technical", 0.0)
    momentum = scores.get("momentum", 0.0)
    insider = scores.get("insider")

    if insider is not None:
        composite = 0.6 * technical + 0.25 * momentum + 0.15 * insider
    else:
        composite = 0.70 * technical + 0.30 * momentum

    return round(max(0.0, min(1.0, composite)), 4)

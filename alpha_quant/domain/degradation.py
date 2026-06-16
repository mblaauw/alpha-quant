"""Data source degradation tracking and fallback multipliers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DegradationStatus(BaseModel):
    model_config = ConfigDict(frozen=True)
    insider_degraded: bool = False
    crowding_degraded: bool = False
    fundamentals_degraded: bool = False
    earnings_stale: bool = False
    sec_degraded: bool = False


def m3_threshold_multiplier(degradation: DegradationStatus) -> float:
    if degradation.crowding_degraded:
        return 1.2
    return 1.0


def blackout_window_days(degradation: DegradationStatus) -> int:
    if degradation.earnings_stale:
        return 4
    return 3

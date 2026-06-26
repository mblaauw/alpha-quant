"""Data source degradation tracking and fallback multipliers.

Degradation is derived from LakeGateway.dataset_health() — per-dataset
staleness and availability determine which mechanisms degrade and whether
price staleness triggers a halt.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from alpha_quant.domain._base import FrozenModel


class DegradationStatus(FrozenModel):
    """Per-dataset degradation flags derived from lake health."""

    insider_degraded: bool = False
    crowding_degraded: bool = False
    fundamentals_degraded: bool = False
    earnings_stale: bool = False


BAR_STALENESS_HOURS_DEFAULT = 30


def health_to_degradation(
    health: dict[str, object], now: datetime | None = None
) -> DegradationStatus:
    """Build DegradationStatus from LakeGateway.dataset_health() output."""
    _ = now
    h = cast("dict[str, Any]", health)
    datasets = cast("dict[str, Any]", h.get("datasets", {}))

    return DegradationStatus(
        fundamentals_degraded=not _dataset_ok(datasets, "fundamentals"),
        insider_degraded=not _dataset_ok(datasets, "insider_tx"),
        crowding_degraded=not _dataset_ok(datasets, "attention"),
    )


def is_price_stale(
    health: dict[str, object],
    staleness_hours: int = BAR_STALENESS_HOURS_DEFAULT,
    now: datetime | None = None,
) -> bool:
    """Check whether the bars dataset is stale beyond the threshold."""
    h = cast("dict[str, Any]", health)
    datasets = cast("dict[str, Any]", h.get("datasets", {}))
    bars = cast("dict[str, Any]", datasets.get("bars", {}))
    if not bars:
        return True
    latest = bars.get("latest_available_at")
    if latest is None:
        return True
    if isinstance(latest, str):
        latest_dt = datetime.fromisoformat(latest.replace("Z", "+00:00"))
    elif isinstance(latest, datetime):
        latest_dt = latest
    else:
        return True
    ref = now or datetime.now(UTC)
    return (ref - latest_dt) > timedelta(hours=staleness_hours)


def _dataset_ok(datasets: dict[str, Any], name: str) -> bool:
    ds = datasets.get(name, {})
    if not isinstance(ds, dict):
        return False
    rc = ds.get("row_count", 0)
    if isinstance(rc, int) and rc > 0:
        return True
    return ds.get("status", "") == "ok"


def m3_threshold_multiplier(degradation: DegradationStatus) -> float:
    if degradation.crowding_degraded:
        return 1.2
    return 1.0


def blackout_window_days(degradation: DegradationStatus) -> int:
    if degradation.earnings_stale:
        return 4
    return 3

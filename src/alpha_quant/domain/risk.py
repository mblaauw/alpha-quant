"""Risk configuration model."""

from __future__ import annotations

from pydantic import Field

from alpha_quant.domain._base import FrozenModel


class RiskConfig(FrozenModel):
    stop_atr_mult: float = Field(default=2.0, ge=0.1, le=10)
    trail_after_r: float = Field(default=1.0, ge=0.1, le=10)
    partial_take_at_r: float = Field(default=2.0, ge=0.1, le=10)
    time_stop_days: int = Field(default=30, ge=1, le=365)
    dd_ladder: list[tuple[float, float]] = Field(default_factory=lambda: [(0.10, 0.5), (0.15, 0.0)])
    dd_window_days: int = 0
    daily_loss_halt_pct: float = Field(default=0.03, ge=0.0, le=1.0)

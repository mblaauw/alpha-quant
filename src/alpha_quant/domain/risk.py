"""Unified risk policy model — all trading thresholds and limits in one place."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from alpha_quant.domain._base import FrozenModel


class RiskPolicyVersion(FrozenModel):
    policy_version_id: str = ""
    version_label: str = ""
    policy_json: str = "{}"
    config_hash: str = ""
    created_at: datetime | None = None


class RiskPolicy(FrozenModel):
    version_label: str = "default"

    @classmethod
    def default(cls) -> RiskPolicy:
        return cls()

    def config_hash(self) -> str:
        import hashlib
        import json

        return hashlib.sha256(
            json.dumps(self.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest()

    stop_atr_mult: float = Field(default=2.0, ge=0.1, le=10.0)
    trail_after_r: float = Field(default=1.0, ge=0.1, le=10.0)
    partial_take_at_r: float = Field(default=2.0, ge=0.1, le=10.0)
    time_stop_days: int = Field(default=30, ge=1, le=365)

    dd_ladder: list[tuple[float, float]] = Field(default_factory=lambda: [(0.10, 0.5), (0.15, 0.0)])
    dd_window_days: int = 0
    drawdown_limit: float = Field(default=-0.10, ge=-1.0, le=0.0)
    daily_loss_limit: float = Field(default=-0.02, ge=-1.0, le=0.0)
    daily_loss_halt_pct: float = Field(default=0.03, ge=0.0, le=1.0)

    gross_exposure_cap: float = Field(default=0.90, ge=0.0, le=2.0)
    var_99_budget: float = Field(default=0.04, ge=0.0, le=1.0)
    sector_cap: float = Field(default=0.70, ge=0.0, le=1.0)
    single_name_cap: float = Field(default=0.25, ge=0.0, le=1.0)

    default_risk_pct: float = Field(default=0.005, ge=0.0, le=1.0)
    buying_power_pct: float = Field(default=0.18, ge=0.0, le=1.0)
    per_trade_risk_cap: float = Field(default=0.01, ge=0.0, le=1.0)
    concentration_cap: float = Field(default=0.20, ge=0.0, le=1.0)

    atr_stop_default_mult: float = Field(default=2.0, ge=0.0, le=10.0)
    atr_stop_aggressive_mult: float = Field(default=2.5, ge=0.0, le=10.0)
    fixed_stop_pct: float = Field(default=0.08, ge=0.0, le=1.0)

    component_flag_multiplier: float = Field(default=1.5, ge=0.0, le=10.0)

    warn_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    equity_floor: float = Field(default=350_000.0, ge=0.0)
    adv_heuristic: float = Field(default=0.02, ge=0.0, le=1.0)
    adv_floor: float = Field(default=1_000_000.0, ge=0.0)

    ewma_lambda: float = Field(default=0.94, ge=0.0, le=1.0)
    hist_window_days: int = Field(default=500, ge=10, le=2000)
    mc_paths: int = Field(default=10000, ge=100, le=1_000_000)

"""Position sizing models (ATR-based, fixed fraction)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SizingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    risk_per_trade_pct: float = 0.01
    max_position_pct: float = 0.15
    max_gross_exposure: float = 0.80
    stop_atr_mult: float = 2.0


class PositionSize(BaseModel):
    model_config = ConfigDict(frozen=True)
    shares: int
    notional: float
    risk_at_stop: float
    capped_by: list[str] = Field(default_factory=list)


def size_position(
    equity: float,
    price: float,
    atr: float,
    regime_mult: float,
    dd_mult: float,
    config: SizingConfig | None = None,
) -> PositionSize:
    cfg = config or SizingConfig()
    capped_by: list[str] = []

    if equity <= 0 or price <= 0 or atr <= 0:
        return PositionSize(shares=0, notional=0.0, risk_at_stop=0.0, capped_by=["invalid_input"])

    if regime_mult <= 0 or dd_mult <= 0:
        return PositionSize(shares=0, notional=0.0, risk_at_stop=0.0, capped_by=["multiplier_zero"])

    risk_notional = equity * cfg.risk_per_trade_pct * regime_mult * dd_mult
    base_notional = risk_notional * price / (cfg.stop_atr_mult * atr)

    max_notional = equity * cfg.max_position_pct
    if base_notional > max_notional:
        capped_by.append("max_position_pct")

    notional = min(base_notional, max_notional)

    notional = max(notional, 0.0)
    shares = int(notional / price) if price > 0 else 0
    actual_notional = shares * price

    if shares == 0:
        caps = capped_by or ["zero_shares"]
        return PositionSize(shares=0, notional=0.0, risk_at_stop=0.0, capped_by=caps)

    risk_at_stop = actual_notional * (cfg.stop_atr_mult * atr / price)

    return PositionSize(
        shares=shares,
        notional=actual_notional,
        risk_at_stop=risk_at_stop,
        capped_by=capped_by,
    )

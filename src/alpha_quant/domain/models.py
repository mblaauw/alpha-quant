"""Core domain models — Position, Decision, Fill, and supporting types."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import Field

from alpha_quant.domain._base import FrozenModel
from alpha_quant.domain.regime import Regime


class Candidate(FrozenModel):
    symbol: str
    date: date
    scores: dict[str, float]
    composite_score: float
    regime: Regime
    gate_results: dict[str, bool]
    block_reason: str | None = None
    sector: str | None = None


class Fill(FrozenModel):
    fill_id: str
    order_id: str
    symbol: str
    quantity: float
    price: float
    timestamp: datetime
    fee: float | None = None


class Position(FrozenModel):
    symbol: str
    quantity: float
    entry_price: float | None = None
    avg_cost: float
    current_price: float | None = None
    stop_price: float | None = None
    trail_price: float | None = None
    market_value: float | None = None
    unrealized_pl: float | None = None
    realized_pl: float | None = None
    sector: str | None = None
    decision_id: str | None = None
    entry_date: date | None = None
    high_since_entry: float | None = None
    partial_taken: bool = False


class Decision(FrozenModel):
    decision_id: str | None = None
    run_id: str | None = None
    symbol: str
    date: date
    action: str
    confidence: float
    reasons: list[str] = Field(default_factory=list)
    candidate: Candidate | None = None
    position: Position | None = None
    risk_results: dict[str, float] = Field(default_factory=dict)
    mechanism_results: dict[str, float] = Field(default_factory=dict)

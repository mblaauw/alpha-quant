"""Core domain models — Bar, Position, Order, Fill, Decision, and all value objects."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Self

from pydantic import Field, model_validator

from alpha_quant.domain._base import FrozenModel
from alpha_quant.domain.regime import Regime


class Bar(FrozenModel):
    symbol: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    adj_close: float | None = None
    fetch_id: str | None = None
    adapter: str | None = None

    @model_validator(mode="after")
    def _validate_bar_relationships(self) -> Self:
        if not (self.low <= self.close <= self.high):
            raise ValueError(
                f"low ({self.low}) <= close ({self.close}) <= high ({self.high}) violated"
            )
        if not (self.low <= self.open <= self.high):
            raise ValueError(
                f"low ({self.low}) <= open ({self.open}) <= high ({self.high}) violated"
            )
        for field in ("open", "high", "low", "close", "volume"):
            if getattr(self, field) < 0:
                raise ValueError(f"{field} must be non-negative, got {getattr(self, field)}")
        return self


class Quote(FrozenModel):
    symbol: str
    timestamp: datetime
    price: float | None = None
    bid: float | None = None
    ask: float | None = None
    bid_size: float | None = None
    ask_size: float | None = None
    volume: float | None = None

    @model_validator(mode="after")
    def _validate_spread(self) -> Self:
        if self.bid is not None and self.ask is not None and self.bid > self.ask:
            raise ValueError(f"bid ({self.bid}) > ask ({self.ask})")
        all_set = self.bid is not None and self.ask is not None and self.price is not None
        if all_set and not (self.bid <= self.price <= self.ask):
            raise ValueError(f"price ({self.price}) not in bid-ask range [{self.bid}, {self.ask}]")
        return self


class FundamentalsSnapshot(FrozenModel):
    symbol: str
    as_of_date: date
    market_cap: float | None = None
    pe_ratio: float | None = None
    eps_ttm: float | None = None
    dividend_yield: float | None = None
    sector: str | None = None
    industry: str | None = None
    operating_cash_flow: float | None = None
    total_liabilities: float | None = None
    total_debt: float | None = None
    total_equity: float | None = None
    revenue: float | None = None
    net_income: float | None = None
    accruals: float | None = None
    fetch_id: str | None = None
    adapter: str | None = None


class Candidate(FrozenModel):
    symbol: str
    date: date
    scores: dict[str, float]
    composite_score: float
    regime: Regime
    gate_results: dict[str, bool]
    block_reason: str | None = None
    sector: str | None = None

    @model_validator(mode="after")
    def _validate_gate_consistency(self) -> Self:
        if self.block_reason is not None and all(self.gate_results.values()):
            raise ValueError(f"block_reason set ({self.block_reason}) but all gates passed")
        return self


class Order(FrozenModel):
    order_id: str
    symbol: str
    action: Literal["buy", "sell"]
    quantity: float
    order_type: Literal["market", "limit", "stop"]
    limit_price: float | None = None
    status: Literal[
        "pending", "submitted", "partially_filled", "filled", "cancelled", "expired", "new"
    ]
    submitted_at: datetime | None = None
    fill_date: datetime | None = None
    filled_quantity: float | None = None
    avg_fill_price: float | None = None

    @model_validator(mode="after")
    def _validate_fill_quantity(self) -> Self:
        if self.filled_quantity is not None and self.filled_quantity > self.quantity:
            raise ValueError(
                f"filled_quantity ({self.filled_quantity}) > quantity ({self.quantity})"
            )
        if self.filled_quantity is not None and self.filled_quantity < 0:
            raise ValueError(f"filled_quantity ({self.filled_quantity}) < 0")
        return self


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
    order: Order | None = None
    risk_results: dict[str, float] = Field(default_factory=dict)
    mechanism_results: dict[str, float] = Field(default_factory=dict)


class CorporateAction(FrozenModel):
    symbol: str
    effective_date: date
    action_type: str
    ratio: float | None = None
    amount: float | None = None
    fetch_id: str | None = None
    adapter: str | None = None


class IndicatorState(FrozenModel):
    symbol: str
    date: date
    values: dict[str, float]
    status: str = "valid"


class PortfolioSnapshot(FrozenModel):
    date: date
    cash: float
    equity: float
    regime: Regime = "CAUTION"
    book: str = "PAPER"

from __future__ import annotations

from datetime import date, datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Bar(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    adj_close: float | None = None
    fetch_id: str | None = None

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
        return self


class Quote(BaseModel):
    model_config = ConfigDict(frozen=True)

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


class TradingDay(BaseModel):
    model_config = ConfigDict(frozen=True)

    date: date
    is_open: bool
    session: str | None = None


class FundamentalsSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

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


class EarningsEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    date: date
    eps_estimate: float | None = None
    eps_actual: float | None = None
    revenue_estimate: float | None = None
    revenue_actual: float | None = None
    fetch_id: str | None = None


class InsiderTransaction(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    filing_date: date | None = None
    transaction_date: date | None = None
    owner: str
    title: str | None = None
    transaction_type: str
    shares_traded: float
    price: float | None = None
    shares_held: float | None = None
    fetch_id: str | None = None


class InsiderCluster(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    cluster_date: date
    num_transactions: int
    net_shares: float
    avg_price: float | None = None
    signal: str | None = None
    value: float | None = None
    transaction_type: str | None = None
    officer_count: int | None = None
    director_count: int | None = None


class MentionCount(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    mention_date: date
    source: str
    count: int
    fetch_id: str | None = None


class SentimentBaseline(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    mean_mentions: float
    std_mentions: float
    z_score: float | None = None


class Candidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    date: date
    scores: dict[str, float]
    composite_score: float
    regime: str
    gate_results: dict[str, bool]
    block_reason: str | None = None
    sector: str | None = None

    @model_validator(mode="after")
    def _validate_gate_consistency(self) -> Self:
        if self.block_reason is not None and all(self.gate_results.values()):
            raise ValueError(f"block_reason set ({self.block_reason}) but all gates passed")
        return self


class Order(BaseModel):
    model_config = ConfigDict(frozen=True)

    order_id: str
    symbol: str
    action: str
    quantity: float
    order_type: str
    limit_price: float | None = None
    status: str
    submitted_at: date | None = None
    fill_date: date | None = None
    filled_quantity: float | None = None
    avg_fill_price: float | None = None

    @model_validator(mode="after")
    def _validate_fill_quantity(self) -> Self:
        if (
            self.filled_quantity is not None
            and self.quantity is not None
            and self.filled_quantity > self.quantity
        ):
            raise ValueError(
                f"filled_quantity ({self.filled_quantity}) > quantity ({self.quantity})"
            )
        return self


class Fill(BaseModel):
    model_config = ConfigDict(frozen=True)

    fill_id: str
    order_id: str
    symbol: str
    quantity: float
    price: float
    timestamp: datetime


class Position(BaseModel):
    model_config = ConfigDict(frozen=True)

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


class Decision(BaseModel):
    model_config = ConfigDict(frozen=True)

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


class UniverseMember(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    price: float | None = None
    dollar_volume_median: float | None = None
    market_cap: float | None = None
    sector: str | None = None
    passes_m1: bool = False
    fail_reason: str | None = None


class TickerRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticker: str
    cik: str
    name: str
    exchange: str | None = None
    sic_code: int | None = None


class CorporateAction(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    effective_date: date
    action_type: str
    ratio: float | None = None
    amount: float | None = None
    fetch_id: str | None = None


class IndicatorState(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    date: date
    values: dict[str, float]
    status: str = "valid"


class PortfolioSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    date: date
    cash: float
    equity: float
    regime: str = "CAUTION"
    book: str = "PAPER"

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


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


class Quote(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    timestamp: datetime
    price: float
    bid: float | None = None
    ask: float | None = None
    volume: float | None = None


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


class EarningsEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    date: date
    eps_estimate: float | None = None
    eps_actual: float | None = None
    revenue_estimate: float | None = None
    revenue_actual: float | None = None


class InsiderTransaction(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    filing_date: date
    transaction_date: date | None = None
    owner: str
    title: str | None = None
    transaction_type: str
    shares_traded: float
    price: float | None = None
    shares_held: float | None = None


class InsiderCluster(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    cluster_date: date
    num_transactions: int
    net_shares: float
    avg_price: float | None = None
    signal: str | None = None


class MentionCount(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    date: date
    source: str
    count: int


class SentimentBaseline(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    mean_mentions: float
    std_mentions: float
    z_score: float | None = None


class Order(BaseModel):
    model_config = ConfigDict(frozen=True)

    order_id: str
    symbol: str
    side: str
    quantity: float
    order_type: str
    limit_price: float | None = None
    status: str
    submitted_at: datetime | None = None
    filled_at: datetime | None = None
    filled_quantity: float | None = None
    avg_fill_price: float | None = None


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
    avg_cost: float
    current_price: float | None = None
    market_value: float | None = None
    unrealized_pl: float | None = None
    realized_pl: float | None = None


class Decision(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    date: date
    action: str
    confidence: float
    reasons: list[str] = []


class IndicatorState(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    date: date
    values: dict[str, float]

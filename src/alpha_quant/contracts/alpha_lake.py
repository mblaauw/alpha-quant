from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class AlphaLakeContract:
    service: str
    api_version: str
    minimum_alpha_quant_version: str
    capabilities: list[str]


@dataclass(frozen=True)
class AlphaLakeHealth:
    status: str = "unknown"
    snapshots: int = 0
    latest_snapshot_id: str | None = None


@dataclass(frozen=True)
class BarObservation:
    effective_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    adj_close: float | None = None


@dataclass(frozen=True)
class IndicatorObservation:
    effective_date: date
    values: dict[str, float | None]


@dataclass(frozen=True)
class FundamentalMetric:
    metric_id: str
    name: str
    category: str
    period_end: str | None = None
    value: float | None = None
    unit: str = ""
    state: str = ""
    tone: str = ""
    quality_status: str = ""
    available_at: str | None = None


@dataclass(frozen=True)
class InsiderTransaction:
    effective_date: str
    transaction_type: str
    shares: float | None = None
    price: float | None = None
    value: float | None = None


@dataclass(frozen=True)
class EarningsEvent:
    effective_date: str
    symbol: str


@dataclass(frozen=True)
class MentionObservation:
    effective_date: str
    count: int
    source: str = "alpha_lake"


@dataclass(frozen=True)
class DecisionPanel:
    as_of: datetime
    snapshot_id: str | None
    symbols: list[str]
    panels: dict[str, SymbolPanel]


@dataclass(frozen=True)
class SymbolPanel:
    symbol: str
    bars: list[BarObservation] = field(default_factory=list)
    indicators: dict[str, list[float | None]] = field(default_factory=dict)
    fundamentals: list[FundamentalMetric] = field(default_factory=list)
    insider_transactions: list[InsiderTransaction] = field(default_factory=list)
    earnings_events: list[EarningsEvent] = field(default_factory=list)
    attention_mentions: list[MentionObservation] = field(default_factory=list)


@dataclass(frozen=True)
class UniverseMember:
    symbol: str
    security_id: str
    name: str = ""


@dataclass(frozen=True)
class UniverseSnapshot:
    as_of: date | None
    members: list[UniverseMember]

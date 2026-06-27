from __future__ import annotations

import datetime
from dataclasses import dataclass, field


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
class ReadoutDefinition:
    readout_id: str
    label: str
    category: str
    unit: str = ""


@dataclass(frozen=True)
class ReadoutObservation:
    effective_date: str
    value: float | None = None
    normalized: float | None = None


@dataclass(frozen=True)
class ReadoutItem:
    definition: ReadoutDefinition
    observations: list[ReadoutObservation] = field(default_factory=list)


@dataclass(frozen=True)
class FactsBundleMetadata:
    symbol: str
    as_of: datetime.datetime
    snapshot_id: str | None = None
    categories: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FactsBundleSections:
    readouts: list[ReadoutItem] = field(default_factory=list)
    fundamentals: list[FundamentalMetric] = field(default_factory=list)
    insider_transactions: list[InsiderTransaction] = field(default_factory=list)
    earnings_events: list[EarningsEvent] = field(default_factory=list)
    attention_mentions: list[MentionObservation] = field(default_factory=list)


@dataclass(frozen=True)
class FactsBundle:
    metadata: FactsBundleMetadata
    sections: FactsBundleSections = field(default_factory=FactsBundleSections)


@dataclass(frozen=True)
class SymbolRegistryItem:
    symbol: str
    added_at: str = ""
    active: bool = True


@dataclass(frozen=True)
class SymbolMutationResult:
    symbol: str
    status: str = ""

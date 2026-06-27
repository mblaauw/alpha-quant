from __future__ import annotations

import datetime
from dataclasses import dataclass, field

# -- Service-level contracts --


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


# -- Neutral observation contracts (Phase 4+) --


@dataclass(frozen=True)
class PriceObservation:
    """Single pre-computed price observation for a symbol.

    No OHLC history — just what policies need.
    """

    latest_close: float
    latest_volume: float
    previous_close: float | None = None
    daily_high: float | None = None
    daily_low: float | None = None
    daily_open: float | None = None


@dataclass(frozen=True)
class TechnicalObservations:
    """Pre-computed technical indicator values for a symbol.

    Named fields for every indicator a policy currently queries.
    """

    rsi_14: float | None = None
    macd_histogram: float | None = None
    atr_pct_14: float | None = None
    ma_regime_50: float | None = None
    ma_regime_200: float | None = None
    volume_ratio_21: float | None = None
    return_63d: float | None = None

    # Catch-all for any indicator not yet promoted to a named field
    additional: dict[str, float | None] = field(default_factory=dict)


# Maps Alpha-Lake indicator key names to TechnicalObservations field names.
# Single source of truth — imported by _parse.py and decision_context.py.
INDICATOR_FIELD_MAP: dict[str, str] = {
    "momentum.rsi_14": "rsi_14",
    "trend.macd_histogram": "macd_histogram",
    "volatility.atr_pct_14": "atr_pct_14",
    "trend.ma_regime_50": "ma_regime_50",
    "trend.ma_regime_200": "ma_regime_200",
    "liquidity.volume_ratio_21": "volume_ratio_21",
    "momentum.return_63d": "return_63d",
}


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
class BarObservation:
    """OHLC bar — provided for pipeline fill simulation and stop tracking only.

    Policies must NOT read bars directly; use PriceObservation / TechnicalObservations.
    """

    effective_date: datetime.date
    open: float
    high: float
    low: float
    close: float
    volume: float
    adj_close: float | None = None

    @property
    def date(self) -> datetime.date:
        return self.effective_date


@dataclass(frozen=True)
class SymbolObservations:
    """All neutral observations for one symbol at one decision point."""

    symbol: str
    price: PriceObservation | None = None
    technical: TechnicalObservations | None = None
    fundamentals: list[FundamentalMetric] = field(default_factory=list)
    insider_transactions: list[InsiderTransaction] = field(default_factory=list)
    earnings_events: list[EarningsEvent] = field(default_factory=list)
    attention_mentions: list[MentionObservation] = field(default_factory=list)
    bars: list[BarObservation] = field(default_factory=list)


@dataclass(frozen=True)
class MarketObservations:
    """Market-wide observations derived from SPY and other broad indices.

    Used by regime_policy to detect RISK_ON / CAUTION / RISK_OFF.
    """

    spy_close: float | None = None
    spy_ma_regime_50: float | None = None
    spy_ma_regime_200: float | None = None
    spy_bar_count: int = 0
    vix_level: float | None = None
    breadth: float | None = None

    @staticmethod
    def from_symbol_observations(
        spy_obs: SymbolObservations | None,
    ) -> MarketObservations:
        if spy_obs is None:
            return MarketObservations()
        return MarketObservations(
            spy_close=spy_obs.price.latest_close if spy_obs.price else None,
            spy_ma_regime_50=spy_obs.technical.ma_regime_50 if spy_obs.technical else None,
            spy_ma_regime_200=spy_obs.technical.ma_regime_200 if spy_obs.technical else None,
            spy_bar_count=len(spy_obs.bars),
        )


@dataclass(frozen=True)
class NeutralObservations:
    """Versioned neutral-observation contract returned by Alpha-Lake.

    Contains everything a single decision run needs.
    """

    as_of: datetime.datetime
    snapshot_id: str | None
    symbols: list[str]
    per_symbol: dict[str, SymbolObservations]
    market: MarketObservations = field(default_factory=MarketObservations)


# -- Legacy contracts (Phase 3, kept for backward compat during migration) --


@dataclass(frozen=True)
class DecisionPanel:
    as_of: datetime.datetime
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
    as_of: datetime.date | None
    members: list[UniverseMember]


# -- Facts-bundle contracts (Phase 4.5+ / Advice Workflow) --


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

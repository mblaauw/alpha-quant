from __future__ import annotations

from datetime import date, datetime

from alpha_quant.contracts.alpha_lake import (
    INDICATOR_FIELD_MAP,
    BarObservation,
    EarningsEvent,
    FundamentalMetric,
    InsiderTransaction,
    MentionObservation,
    NeutralObservations,
    SymbolObservations,
    TechnicalObservations,
)


class DecisionContext:
    """Encapsulates all Alpha-Lake neutral observations for a single decision point.

    Policy modules receive a DecisionContext and extract the facts they need.
    No policy module may access raw bars, statements, or provider data.

    Backed by NeutralObservations (Phase 4 contract) instead of DecisionPanel.
    """

    def __init__(self, observations: NeutralObservations, symbol: str) -> None:
        self._obs = observations
        self._symbol = symbol
        self._so = observations.per_symbol.get(symbol) or SymbolObservations(symbol=symbol)

    @property
    def as_of(self) -> datetime:
        return self._obs.as_of

    @property
    def snapshot_id(self) -> str | None:
        return self._obs.snapshot_id

    @property
    def symbol(self) -> str:
        return self._symbol

    # -- Neutral observations accessors --

    @property
    def market(self) -> object:
        return self._obs.market

    # -- Bars (operational — for pipeline fill simulation only) --

    @property
    def bars(self) -> list[BarObservation]:
        return self._so.bars

    def latest_close(self) -> float | None:
        if self._so.price is not None:
            return self._so.price.latest_close
        if self._so.bars:
            return self._so.bars[-1].close
        return None

    def latest_volume(self) -> float | None:
        if self._so.price is not None:
            return self._so.price.latest_volume
        if self._so.bars:
            return self._so.bars[-1].volume
        return None

    # -- Technical indicators (structured observation fields + fallback) --

    def indicator(self, name: str) -> float | None:
        tech = self._so.technical
        if tech is not None:
            val = _get_technical_field(tech, name)
            if val is not None:
                return val
        return None

    def indicator_series(self, name: str) -> list[float | None]:
        # From neutral observations we only have the latest value;
        # series access is a legacy pattern. Return a single-element
        # list if the named indicator exists, otherwise empty.
        tech = self._so.technical
        if tech is not None:
            val = _get_technical_field(tech, name)
            if val is not None:
                return [val]
        return []

    # -- Fundamentals --

    def fundamental(self, metric_id: str) -> FundamentalMetric | None:
        for m in self._so.fundamentals:
            if m.metric_id == metric_id:
                return m
        return None

    def fundamental_value(self, metric_id: str) -> float | None:
        m = self.fundamental(metric_id)
        return m.value if m else None

    def fundamental_tone(self, metric_id: str) -> str | None:
        m = self.fundamental(metric_id)
        return m.tone if m else None

    def all_fundamentals(self) -> list[FundamentalMetric]:
        return list(self._so.fundamentals)

    # -- Insider --

    @property
    def insider_transactions(self) -> list[InsiderTransaction]:
        return list(self._so.insider_transactions)

    # -- Earnings --

    @property
    def earnings_events(self) -> list[EarningsEvent]:
        return list(self._so.earnings_events)

    def has_future_earnings(self, as_of: date) -> bool:
        return any(
            e.effective_date
            and isinstance(e.effective_date, str)
            and datetime.fromisoformat(e.effective_date.replace("Z", "+00:00")).date() >= as_of
            for e in self._so.earnings_events
        )

    # -- Attention --

    @property
    def attention_mentions(self) -> list[MentionObservation]:
        return list(self._so.attention_mentions)


def _get_technical_field(tech: TechnicalObservations, name: str) -> float | None:
    field = INDICATOR_FIELD_MAP.get(name)
    if field is not None:
        return getattr(tech, field, None)
    return tech.additional.get(name)

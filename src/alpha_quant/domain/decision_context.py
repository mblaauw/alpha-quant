from __future__ import annotations

from datetime import date, datetime

from alpha_quant.contracts.alpha_lake import (
    BarObservation,
    DecisionPanel,
    EarningsEvent,
    FundamentalMetric,
    InsiderTransaction,
    MentionObservation,
    SymbolPanel,
)


class DecisionContext:
    """Encapsulates all Alpha-Lake facts for a single decision point.

    Policy modules receive a DecisionContext and extract the facts they need.
    No policy module may access raw bars, statements, or provider data.
    """

    def __init__(self, panel: DecisionPanel, symbol: str) -> None:
        self._panel = panel
        self._symbol = symbol
        self._sp = panel.panels.get(symbol) or SymbolPanel(symbol=symbol)

    @property
    def as_of(self) -> datetime:
        return self._panel.as_of

    @property
    def snapshot_id(self) -> str | None:
        return self._panel.snapshot_id

    @property
    def symbol(self) -> str:
        return self._symbol

    # -- Bars --

    @property
    def bars(self) -> list[BarObservation]:
        return self._sp.bars

    def latest_close(self) -> float | None:
        if not self._sp.bars:
            return None
        return self._sp.bars[-1].close

    def latest_volume(self) -> float | None:
        if not self._sp.bars:
            return None
        return self._sp.bars[-1].volume

    # -- Technical indicators --

    def indicator(self, name: str) -> float | None:
        series = self._sp.indicators.get(name)
        if series and len(series) > 0:
            return series[-1]
        return None

    def indicator_series(self, name: str) -> list[float | None]:
        return self._sp.indicators.get(name, [])

    # -- Fundamentals --

    def fundamental(self, metric_id: str) -> FundamentalMetric | None:
        for m in self._sp.fundamentals:
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
        return list(self._sp.fundamentals)

    # -- Insider --

    @property
    def insider_transactions(self) -> list[InsiderTransaction]:
        return list(self._sp.insider_transactions)

    # -- Earnings --

    @property
    def earnings_events(self) -> list[EarningsEvent]:
        return list(self._sp.earnings_events)

    def has_future_earnings(self, as_of: date) -> bool:
        return any(
            e.effective_date
            and isinstance(e.effective_date, str)
            and datetime.fromisoformat(e.effective_date.replace("Z", "+00:00")).date() >= as_of
            for e in self._sp.earnings_events
        )

    # -- Attention --

    @property
    def attention_mentions(self) -> list[MentionObservation]:
        return list(self._sp.attention_mentions)

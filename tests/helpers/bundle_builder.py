"""FactsBundleBuilder — construct FactsBundle instances for tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from alpha_quant.contracts.alpha_lake import (
    EarningsEvent,
    FactsBundle,
    FactsBundleMetadata,
    FactsBundleSections,
    FundamentalMetric,
    InsiderTransaction,
    MentionObservation,
    ReadoutDefinition,
    ReadoutItem,
    ReadoutObservation,
)


class FactsBundleBuilder:
    """Builder for constructing FactsBundle instances with fluent API."""

    def __init__(self, symbol: str = "TEST") -> None:
        self._symbol = symbol
        self._as_of = datetime(2026, 1, 5, 14, 0, 0, tzinfo=UTC)
        self._snapshot_id: str | None = None
        self._categories: list[str] = []
        self._readouts: list[ReadoutItem] = []
        self._fundamentals: list[FundamentalMetric] = []
        self._insider_tx: list[InsiderTransaction] = []
        self._earnings: list[EarningsEvent] = []
        self._mentions: list[MentionObservation] = []

    def as_of(self, dt: datetime) -> FactsBundleBuilder:
        self._as_of = dt
        return self

    def snapshot(self, sid: str) -> FactsBundleBuilder:
        self._snapshot_id = sid
        return self

    def with_readout(
        self,
        readout_id: str,
        value: float,
        label: str = "",
        category: str = "",
        effective_date: str = "",
    ) -> FactsBundleBuilder:
        self._readouts.append(
            ReadoutItem(
                definition=ReadoutDefinition(
                    readout_id=readout_id,
                    label=label or readout_id,
                    category=category,
                ),
                observations=[
                    ReadoutObservation(
                        effective_date=effective_date or self._as_of.date().isoformat(),
                        value=value,
                    )
                ],
            )
        )
        if category and category not in self._categories:
            self._categories.append(category)
        return self

    def with_price_last(self, price: float) -> FactsBundleBuilder:
        return self.with_readout("price.last", price, "Last Price", "price")

    def with_rsi(self, rsi: float = 55.0) -> FactsBundleBuilder:
        return self.with_readout("momentum.rsi_14", rsi, "RSI(14)", "momentum")

    def with_macd(self, macd: float = 0.0) -> FactsBundleBuilder:
        return self.with_readout("momentum.macd_cross", macd, "MACD Cross", "momentum")

    def with_trend_regime(self, regime: float = 50.0) -> FactsBundleBuilder:
        return self.with_readout("trend.regime", regime, "Trend Regime", "trend")

    def with_volatility(
        self, atr: float = 1.5, bollinger: float = 0.10, vol_regime: float = 50.0
    ) -> FactsBundleBuilder:
        self = self.with_readout("volatility.atr_percent", atr, "ATR %", "volatility")
        self = self.with_readout(
            "volatility.bollinger_width", bollinger, "Bollinger Width", "volatility"
        )
        self = self.with_readout("volatility.regime", vol_regime, "Vol Regime", "volatility")
        return self

    def with_volume_ratio(self, rvol: float = 1.0) -> FactsBundleBuilder:
        return self.with_readout("participation.rvol", rvol, "Relative Volume", "participation")

    def with_relative_strength(self, vs_benchmark: float = 0.0) -> FactsBundleBuilder:
        return self.with_readout(
            "relative_strength.vs_benchmark", vs_benchmark, "vs Benchmark", "relative_strength"
        )

    def with_full_technical(
        self,
        rsi: float = 55.0,
        macd: float = 0.0,
        trend: float = 50.0,
        atr: float = 1.5,
        bollinger: float = 0.10,
        vol_regime: float = 50.0,
        rvol: float = 1.0,
        rs: float = 0.0,
    ) -> FactsBundleBuilder:
        self = self.with_rsi(rsi).with_macd(macd).with_trend_regime(trend)
        self = self.with_volatility(atr, bollinger, vol_regime)
        self = self.with_volume_ratio(rvol).with_relative_strength(rs)
        return self

    def with_fundamental(
        self, metric_id: str, value: float | None, name: str = "", category: str = ""
    ) -> FactsBundleBuilder:
        self._fundamentals.append(
            FundamentalMetric(
                metric_id=metric_id,
                name=name or metric_id,
                category=category or "",
                value=value,
            )
        )
        return self

    def with_pe(self, pe: float) -> FactsBundleBuilder:
        return self.with_fundamental("pe_ttm", pe, "PE TTM", "valuation")

    def with_earnings(self, effective_date: str, symbol: str | None = None) -> FactsBundleBuilder:
        self._earnings.append(
            EarningsEvent(
                effective_date=effective_date,
                symbol=symbol or self._symbol,
            )
        )
        return self

    def build(self) -> FactsBundle:
        return FactsBundle(
            metadata=FactsBundleMetadata(
                symbol=self._symbol,
                as_of=self._as_of,
                snapshot_id=self._snapshot_id,
                categories=self._categories,
            ),
            sections=FactsBundleSections(
                readouts=self._readouts,
                fundamentals=self._fundamentals,
                insider_transactions=self._insider_tx,
                earnings_events=self._earnings,
                attention_mentions=self._mentions,
            ),
        )


def make_default_bundle(symbol: str = "TEST", **overrides: Any) -> FactsBundle:
    """Quick default bundle with full technical indicators at neutral values."""
    builder = FactsBundleBuilder(symbol).with_full_technical()
    if overrides:
        for key, val in overrides.items():
            method = getattr(builder, f"with_{key}", None)
            if method:
                if isinstance(val, dict):
                    method(**val)
                else:
                    method(val)
    return builder.build()

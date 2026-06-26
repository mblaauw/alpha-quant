from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, override

from alpha_quant.adapters._parse import (
    opt_float,
    parse_date,
    parse_symbol_observations,
)
from alpha_quant.contracts.alpha_lake import (
    AlphaLakeContract,
    AlphaLakeHealth,
    BarObservation,
    DecisionPanel,
    EarningsEvent,
    FundamentalMetric,
    InsiderTransaction,
    MarketObservations,
    MentionObservation,
    NeutralObservations,
    SymbolObservations,
    SymbolPanel,
    UniverseMember,
    UniverseSnapshot,
)
from alpha_quant.ports.alpha_lake import AlphaLakeReadPort


class AlphaLakeHttpFixtureClient(AlphaLakeReadPort):
    """Reads prerecorded Alpha-Lake HTTP responses from fixture files.

    Used for offline deterministic replay and testing.
    No live HTTP calls are made.
    """

    def __init__(self, fixture_path: Path) -> None:
        self._root = fixture_path

    @override
    def health(self) -> AlphaLakeHealth:
        return self._load("health", AlphaLakeHealth) or AlphaLakeHealth(status="ok")

    @override
    def contract(self) -> AlphaLakeContract:
        return self._load("contract", AlphaLakeContract) or AlphaLakeContract(
            service="alpha-lake",
            api_version="1.0",
            minimum_alpha_quant_version="0.3.0",
            capabilities=[
                "pit_bars",
                "technical_indicators",
                "fundamental_metrics",
                "insider_facts",
                "earnings_events",
                "attention_metrics",
                "snapshot_reads",
            ],
        )

    @override
    def read_universe(self, as_of: date | None = None) -> UniverseSnapshot:
        data = self._load_json("universe")
        if data:
            return UniverseSnapshot(
                as_of=as_of,
                members=[UniverseMember(**m) for m in data.get("members", [])],
            )
        return UniverseSnapshot(as_of=as_of, members=[])

    @override
    def read_decision_panel(
        self,
        symbols: list[str],
        as_of: datetime,
        snapshot_id: str | None = None,
    ) -> DecisionPanel:
        return _legacy_panel(self._load_panel_data, symbols, as_of, snapshot_id)

    @override
    def read_replay_panel(
        self,
        symbols: list[str],
        as_of: datetime,
        snapshot_id: str,
    ) -> DecisionPanel:
        return _legacy_panel(self._load_panel_data, symbols, as_of, snapshot_id)

    @override
    def read_observations(
        self,
        symbols: list[str],
        as_of: datetime,
        snapshot_id: str | None = None,
    ) -> NeutralObservations:
        data = self._load_panel_data(symbols)
        per_symbol: dict[str, SymbolObservations] = {}
        for symbol, raw in data.get("panels", {}).items():
            per_symbol[symbol] = parse_symbol_observations(symbol, raw)

        spy_obs = per_symbol.get("SPY")
        return NeutralObservations(
            as_of=as_of,
            snapshot_id=snapshot_id,
            symbols=symbols,
            per_symbol=per_symbol,
            market=MarketObservations.from_symbol_observations(spy_obs),
        )

    @override
    def close(self) -> None:
        pass

    def _load_panel_data(self, symbols: list[str]) -> dict[str, Any]:
        key = f"decision-panel-{'-'.join(sorted(symbols))}"
        data = self._load_json(key)
        if not data:
            data = self._load_json("decision-panel")
        if not data:
            return {"panels": {}}
        return data

    def _load(self, name: str, cls: type) -> Any | None:
        data = self._load_json(name)
        if data:
            try:
                return cls(**data)
            except TypeError:
                pass
        return None

    def _load_json(self, name: str) -> dict[str, Any] | None:
        path = self._root / f"{name}.json"
        if path.exists():
            return json.loads(path.read_text())
        return None


def _legacy_panel(
    loader: Any,
    symbols: list[str],
    as_of: datetime,
    snapshot_id: str | None = None,
) -> DecisionPanel:
    data = loader(symbols)
    if not data.get("panels"):
        return DecisionPanel(as_of=as_of, snapshot_id=snapshot_id, symbols=symbols, panels={})

    panels: dict[str, SymbolPanel] = {}
    for symbol, raw in data.get("panels", {}).items():
        bars = [_legacy_parse_bar(b) for b in raw.get("bars", [])]
        indicators = _legacy_parse_indicators(raw.get("indicators", {}))
        fundamentals = [_legacy_parse_fundamental(m) for m in raw.get("fundamentals", [])]
        insider = [_legacy_parse_insider(t) for t in raw.get("insider_transactions", [])]
        earnings = [_legacy_parse_earnings(e) for e in raw.get("earnings_events", [])]
        mentions = [_legacy_parse_mention(m) for m in raw.get("attention_mentions", [])]
        panels[symbol] = SymbolPanel(
            symbol=symbol,
            bars=bars,
            indicators=indicators,
            fundamentals=fundamentals,
            insider_transactions=insider,
            earnings_events=earnings,
            attention_mentions=mentions,
        )

    return DecisionPanel(
        as_of=as_of,
        snapshot_id=snapshot_id,
        symbols=symbols,
        panels=panels,
    )


def _legacy_parse_bar(row: dict[str, Any]) -> BarObservation:
    return BarObservation(
        effective_date=parse_date(row.get("effective_date") or row.get("date")),
        open=float(row.get("open", 0.0)),
        high=float(row.get("high", 0.0)),
        low=float(row.get("low", 0.0)),
        close=float(row.get("close", 0.0)),
        volume=float(row.get("volume", 0.0)),
        adj_close=opt_float(row.get("adj_close") or row.get("adjusted_close")),
    )


def _legacy_parse_indicators(raw: dict[str, list[Any]]) -> dict[str, list[float | None]]:
    result: dict[str, list[float | None]] = {}
    for key, values in raw.items():
        if key in (
            "effective_date",
            "security_id",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "source_id",
        ):
            continue
        result[key] = [float(v) if v is not None else None for v in values]
    return result


def _legacy_parse_fundamental(row: dict[str, Any]) -> FundamentalMetric:
    return FundamentalMetric(
        metric_id=row.get("metric_id", ""),
        name=row.get("name", ""),
        category=row.get("category", ""),
        period_end=row.get("period_end"),
        value=opt_float(row.get("value")),
        unit=row.get("unit", ""),
        state=row.get("state", ""),
        tone=row.get("tone", ""),
        quality_status=row.get("quality_status", ""),
        available_at=row.get("available_at"),
    )


def _legacy_parse_insider(row: dict[str, Any]) -> InsiderTransaction:
    return InsiderTransaction(
        effective_date=str(row.get("effective_date", "")),
        transaction_type=str(row.get("transaction_code", row.get("transaction_type", ""))),
        shares=opt_float(row.get("shares")),
        price=opt_float(row.get("price")),
        value=opt_float(row.get("value")),
    )


def _legacy_parse_earnings(row: dict[str, Any]) -> EarningsEvent:
    return EarningsEvent(
        effective_date=str(row.get("effective_date", "")),
        symbol=str(row.get("symbol", row.get("security_id", ""))),
    )


def _legacy_parse_mention(row: dict[str, Any]) -> MentionObservation:
    return MentionObservation(
        effective_date=str(row.get("effective_date", "")),
        count=int(row.get("mention_count", row.get("count", 0))),
        source=str(row.get("source_id", "alpha_lake")),
    )

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, override

from alpha_quant.adapters._parse import (
    parse_bar_obs,
    parse_earnings_obs,
    parse_facts_bundle,
    parse_fundamental_obs,
    parse_insider_obs,
    parse_mention_obs,
    parse_symbol_observations,
    parse_symbol_registry_item,
)
from alpha_quant.contracts.alpha_lake import (
    AlphaLakeContract,
    AlphaLakeHealth,
    DecisionPanel,
    FactsBundle,
    FactsBundleMetadata,
    MarketObservations,
    NeutralObservations,
    SymbolMutationResult,
    SymbolObservations,
    SymbolPanel,
    SymbolRegistryItem,
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
    def read_facts_bundle(
        self,
        symbol: str,
        as_of: datetime,
        snapshot_id: str | None = None,
        *,
        categories: list[str] | None = None,
        readout_ids: list[str] | None = None,
        metric_ids: list[str] | None = None,
    ) -> FactsBundle:
        key = f"facts-bundle-{symbol}"
        data = self._load_json(key)
        if not data:
            data = self._load_json("facts-bundle")
        if not data:
            return FactsBundle(
                metadata=FactsBundleMetadata(
                    symbol=symbol,
                    as_of=as_of,
                    snapshot_id=snapshot_id,
                    categories=categories or [],
                )
            )
        return parse_facts_bundle(data)

    @override
    def read_facts_bundle_batch(
        self,
        symbols: list[str],
        as_of: datetime,
        snapshot_id: str | None = None,
        *,
        categories: list[str] | None = None,
        readout_ids: list[str] | None = None,
        metric_ids: list[str] | None = None,
    ) -> dict[str, FactsBundle]:
        key = f"facts-bundle-batch-{'-'.join(sorted(symbols))}"
        data = self._load_json(key)
        if not data:
            data = self._load_json("facts-bundle-batch")
        if not data:
            return {sym: self.read_facts_bundle(sym, as_of, snapshot_id) for sym in symbols}
        return {sym: parse_facts_bundle(b) for sym, b in data.items()}

    @override
    def list_symbols(self, active_only: bool = True) -> list[SymbolRegistryItem]:
        raw = self._load_json("symbols")
        if not raw:
            return []
        items: list[Any] = raw if isinstance(raw, list) else raw.get("symbols", [])
        return [parse_symbol_registry_item(d) for d in items if isinstance(d, dict)]

    @override
    def add_symbol(self, symbol: str) -> SymbolMutationResult:
        return SymbolMutationResult(symbol=symbol, status="added")

    @override
    def remove_symbol(self, symbol: str) -> SymbolMutationResult:
        return SymbolMutationResult(symbol=symbol, status="removed")

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

    @override
    def get_freshness(self, symbols: list[str]) -> dict[str, datetime]:
        now = datetime.now(UTC)
        return {s: now for s in symbols}

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
        bars = [parse_bar_obs(b) for b in raw.get("bars", [])]
        indicators = _legacy_parse_indicators(raw.get("indicators", {}))
        fundamentals = [parse_fundamental_obs(m) for m in raw.get("fundamentals", [])]
        insider = [parse_insider_obs(t) for t in raw.get("insider_transactions", [])]
        earnings = [parse_earnings_obs(e) for e in raw.get("earnings_events", [])]
        mentions = [parse_mention_obs(m) for m in raw.get("attention_mentions", [])]
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


def _legacy_parse_indicators(raw: dict[str, list[Any]]) -> dict[str, list[float | None]]:
    skip_keys = {
        "effective_date",
        "security_id",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "source_id",
        "available_at",
        "ingested_at",
        "source_published_at",
        "validated_at",
        "source_fetch_id",
        "raw_payload_hash",
        "ingestion_run_id",
        "content_hash",
        "version_hash",
        "quality_status",
        "normalization_version",
        "schema_version",
        "parser_version",
    }
    result: dict[str, list[float | None]] = {}
    for key, values in raw.items():
        if key in skip_keys:
            continue
        result[key] = [float(v) if v is not None else None for v in values]
    return result

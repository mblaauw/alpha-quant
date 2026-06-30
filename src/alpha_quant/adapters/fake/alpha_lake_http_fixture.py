from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, override

from alpha_quant.adapters._parse import (
    parse_facts_bundle,
    parse_symbol_registry_item,
)
from alpha_quant.contracts.alpha_lake import (
    AlphaLakeContract,
    AlphaLakeHealth,
    FactsBundle,
    FactsBundleMetadata,
    SymbolMutationResult,
    SymbolRegistryItem,
)
from alpha_quant.ports.alpha_lake import AlphaLakeReadPort


class AlphaLakeHttpFixtureClient(AlphaLakeReadPort):
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
    def get_freshness(self, symbols: list[str]) -> dict[str, datetime]:
        now = datetime.now(UTC)
        return {s: now for s in symbols}

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
        data = self._load_bundle_by_date(symbol, as_of)
        if not data:
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

    def _load_bundle_by_date(self, symbol: str, as_of: datetime) -> dict[str, Any] | None:
        """Try loading a facts-bundle from a date-specific subdirectory."""
        date_str = as_of.date().isoformat()
        path = self._root / date_str / f"facts-bundle-{symbol}.json"
        if path.exists():
            return json.loads(path.read_text())
        # Try stale directory
        stale_path = self._root / "stale" / f"facts-bundle-{symbol}.json"
        if stale_path.exists():
            return json.loads(stale_path.read_text())
        return None

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

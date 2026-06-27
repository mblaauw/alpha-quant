from __future__ import annotations

from datetime import date, datetime
from typing import Protocol

from alpha_quant.contracts.alpha_lake import (
    AlphaLakeContract,
    AlphaLakeHealth,
    DecisionPanel,
    FactsBundle,
    NeutralObservations,
    SymbolMutationResult,
    SymbolRegistryItem,
    UniverseSnapshot,
)


class AlphaLakeReadPort(Protocol):
    def health(self) -> AlphaLakeHealth: ...
    def contract(self) -> AlphaLakeContract: ...
    def read_universe(self, as_of: date | None = None) -> UniverseSnapshot: ...
    def get_freshness(self, symbols: list[str]) -> dict[str, datetime]: ...

    def read_decision_panel(
        self,
        symbols: list[str],
        as_of: datetime,
        snapshot_id: str | None = None,
    ) -> DecisionPanel: ...
    def read_replay_panel(
        self,
        symbols: list[str],
        as_of: datetime,
        snapshot_id: str,
    ) -> DecisionPanel: ...

    # -- Phase 4 neutral-observation contract --

    def read_observations(
        self,
        symbols: list[str],
        as_of: datetime,
        snapshot_id: str | None = None,
    ) -> NeutralObservations: ...

    # -- Phase 4.5+ facts-bundle contract --

    def read_facts_bundle(
        self,
        symbol: str,
        as_of: datetime,
        snapshot_id: str | None = None,
        *,
        categories: list[str] | None = None,
        readout_ids: list[str] | None = None,
        metric_ids: list[str] | None = None,
    ) -> FactsBundle: ...

    def read_facts_bundle_batch(
        self,
        symbols: list[str],
        as_of: datetime,
        snapshot_id: str | None = None,
        *,
        categories: list[str] | None = None,
        readout_ids: list[str] | None = None,
        metric_ids: list[str] | None = None,
    ) -> dict[str, FactsBundle]: ...

    def list_symbols(self, active_only: bool = True) -> list[SymbolRegistryItem]: ...

    def add_symbol(self, symbol: str) -> SymbolMutationResult: ...

    def remove_symbol(self, symbol: str) -> SymbolMutationResult: ...

    def close(self) -> None: ...

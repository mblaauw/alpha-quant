from __future__ import annotations

from datetime import datetime
from typing import Protocol

from alpha_quant.contracts.alpha_lake import (
    AlphaLakeContract,
    AlphaLakeHealth,
    FactsBundle,
    SymbolMutationResult,
    SymbolRegistryItem,
)


class AlphaLakeReadPort(Protocol):
    def health(self) -> AlphaLakeHealth: ...
    def contract(self) -> AlphaLakeContract: ...
    def get_freshness(self, symbols: list[str]) -> dict[str, datetime]: ...

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

    def list_symbols(self, active_only: bool = True) -> list[SymbolRegistryItem]: ...

    def add_symbol(self, symbol: str) -> SymbolMutationResult: ...

    def remove_symbol(self, symbol: str) -> SymbolMutationResult: ...

    def close(self) -> None: ...

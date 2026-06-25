from __future__ import annotations

from datetime import date, datetime
from typing import Protocol

from alpha_quant.contracts.alpha_lake import (
    AlphaLakeContract,
    AlphaLakeHealth,
    DecisionPanel,
    UniverseSnapshot,
)


class AlphaLakeReadPort(Protocol):
    def health(self) -> AlphaLakeHealth: ...
    def contract(self) -> AlphaLakeContract: ...
    def read_universe(self, as_of: date | None = None) -> UniverseSnapshot: ...
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
    def close(self) -> None: ...

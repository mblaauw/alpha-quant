"""Freshness service — per-symbol data freshness against Alpha-Lake.

Provides the backend for the freshness pill in the masthead, per-symbol
freshness badges on every screen, and the freshness gate in the decision pipeline.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from alpha_quant.ports.alpha_lake import AlphaLakeReadPort


def _classify(age_minutes: float, sla_minutes: int, critical_minutes: int) -> str:
    if age_minutes <= sla_minutes:
        return "live"
    if age_minutes <= critical_minutes:
        return "warn"
    return "critical"


class FreshnessService:
    """Wraps Alpha-Lake's latest-bar timestamps and applies freshness SLA."""

    def __init__(self, lake: AlphaLakeReadPort, sla_minutes: int, critical_minutes: int) -> None:
        self._lake = lake
        self._sla = sla_minutes
        self._critical = critical_minutes

    def for_symbol(self, symbol: str) -> dict[str, Any]:
        return self.for_symbols([symbol])[0]

    def for_symbols(self, symbols: list[str]) -> list[dict[str, Any]]:
        now = datetime.now(UTC)
        lake_timestamps = self._lake.get_freshness(symbols)
        result: list[dict[str, Any]] = []
        for sym in symbols:
            ts = lake_timestamps.get(sym, now)
            age = (now - ts).total_seconds() / 60.0
            stale = age > self._sla
            severity = _classify(age, self._sla, self._critical)
            result.append(
                {
                    "symbol": sym,
                    "age_minutes": round(age, 1),
                    "stale": stale,
                    "severity": severity,
                    "last_lake_update": ts.isoformat(),
                }
            )
        return result

    def summary(self, symbols: list[str] | None = None) -> dict[str, Any]:
        batch = self.for_symbols(symbols or [])
        fresh = [s for s in batch if not s["stale"]]
        stale = [s for s in batch if s["stale"]]
        return {
            "as_of": datetime.now(UTC).isoformat(),
            "sla_minutes": self._sla,
            "fresh_count": len(fresh),
            "stale_count": len(stale),
            "symbols": batch,
        }

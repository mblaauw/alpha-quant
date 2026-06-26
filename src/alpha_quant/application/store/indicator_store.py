from __future__ import annotations

import json
from datetime import date
from typing import override

import duckdb

from alpha_quant.domain.models import IndicatorState
from alpha_quant.ports.store import IndicatorStore


class IndicatorStoreMixin(IndicatorStore):
    _state_conn: duckdb.DuckDBPyConnection

    @override
    def save_indicator_state(self, state: IndicatorState) -> None:
        self._state_conn.execute(
            "INSERT OR REPLACE INTO indicator_state (symbol, effective_date, data) "
            "VALUES (?, ?, ?)",
            [state.symbol, str(state.date), json.dumps(state.model_dump(mode="json"))],
        )

    @override
    def load_indicator_state(self, symbol: str, dt: date) -> IndicatorState | None:
        row = self._state_conn.execute(
            "SELECT data FROM indicator_state WHERE symbol = ? AND effective_date = ?",
            [symbol, str(dt)],
        ).fetchone()
        if row:
            return IndicatorState.model_validate(row[0])
        return None

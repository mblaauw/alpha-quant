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
            "INSERT OR REPLACE INTO indicator_state"
            " (symbol, state_date, values, status) VALUES (?, ?, ?, ?)",
            [state.symbol, state.date, json.dumps(state.values), state.status],
        )

    @override
    def load_indicator_state(self, symbol: str, dt: date) -> IndicatorState | None:
        row = self._state_conn.execute(
            "SELECT symbol, state_date, values, status"
            " FROM indicator_state WHERE symbol = ? AND state_date = ?",
            [symbol, dt],
        ).fetchone()
        if row is None:
            return None
        return IndicatorState(
            symbol=row[0],
            date=row[1],
            values=json.loads(row[2]),
            status=row[3],
        )

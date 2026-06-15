from __future__ import annotations

import json
from datetime import date
from typing import override

import duckdb

from alpha_quant.domain.models import Candidate, Decision, Order, Position
from alpha_quant.ports.store import DecisionStore


class DecisionStoreMixin(DecisionStore):
    _state_conn: duckdb.DuckDBPyConnection

    @override
    def save_decision(self, decision: Decision) -> None:
        self._state_conn.execute(
            "INSERT OR REPLACE INTO decisions"
            " (decision_id, run_id, symbol, decision_date, action, confidence, reasons,"
            "  candidate_json, position_json, order_json, risk_results, mechanism_results)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                decision.decision_id,
                decision.run_id,
                decision.symbol,
                decision.date,
                decision.action,
                decision.confidence,
                json.dumps(decision.reasons),
                decision.candidate.model_dump_json() if decision.candidate else None,
                decision.position.model_dump_json() if decision.position else None,
                decision.order.model_dump_json() if decision.order else None,
                json.dumps(decision.risk_results),
                json.dumps(decision.mechanism_results),
            ],
        )

    @override
    def load_decisions(self, symbol: str, since: date) -> list[Decision]:
        rows = self._state_conn.execute(
            "SELECT decision_id, run_id, symbol, decision_date, action, confidence, reasons,"
            " candidate_json, position_json, order_json, risk_results, mechanism_results"
            " FROM decisions WHERE symbol = ? AND decision_date >= ?"
            " ORDER BY decision_date DESC",
            [symbol, since],
        ).fetchall()
        return [
            Decision(
                decision_id=r[0],
                run_id=r[1],
                symbol=r[2],
                date=r[3],
                action=r[4],
                confidence=r[5],
                reasons=json.loads(r[6]) if r[6] else [],
                candidate=Candidate.model_validate_json(r[7]) if r[7] else None,
                position=Position.model_validate_json(r[8]) if r[8] else None,
                order=Order.model_validate_json(r[9]) if r[9] else None,
                risk_results=json.loads(r[10]) if r[10] else {},
                mechanism_results=json.loads(r[11]) if r[11] else {},
            )
            for r in rows
        ]

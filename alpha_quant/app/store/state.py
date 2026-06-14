"""DuckDB state store operations.

Split from app/store.py — no behavior change.
"""

import json
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Self, cast, override

import duckdb
import structlog

from alpha_quant.app.store.canonical import (
    load_corp_actions,
    load_earnings,
    read_bars,
    read_fundamentals,
    read_insider_transactions,
    read_mentions,
    write_dataset,
)
from alpha_quant.domain.events import DomainEvent
from alpha_quant.domain.journal import JournalEntry
from alpha_quant.domain.models import (
    Bar,
    Candidate,
    CorporateAction,
    Decision,
    EarningsEntry,
    Fill,
    FundamentalsSnapshot,
    IndicatorState,
    InsiderTransaction,
    MentionCount,
    Order,
    PortfolioSnapshot,
    Position,
)
from alpha_quant.domain.reporting import ReportEntry, ReportType
from alpha_quant.ports.store import Store

logger = structlog.get_logger()


class CanonicalStore(Store):
    def __init__(self, base_path: str | Path) -> None:
        self._base = Path(base_path)
        self._base.mkdir(parents=True, exist_ok=True)

        self._analytical = duckdb.connect()
        self._analytical.execute("SET threads TO 1")

        self._state_path = self._base / "state.db"
        self._state_conn = duckdb.connect(str(self._state_path))
        self._init_state_schema()

    @contextmanager
    def transaction(self) -> Generator[Self]:
        self._state_conn.execute("BEGIN TRANSACTION")
        try:
            yield self
        except Exception:
            self._state_conn.execute("ROLLBACK")
            raise
        self._state_conn.execute("COMMIT")

    def _canonical_path(self, dataset: str) -> Path:
        return self._base / "canonical" / dataset

    # ---- Analytical store (Parquet via DuckDB) ----

    def _write_dataset(self, models: list[Any], dataset: str) -> None:
        write_dataset(self._analytical, self._base, models, dataset)

    def _write_bars(self, bars: list[Bar]) -> None:
        self._write_dataset(bars, "bars")

    def _write_fundamentals(self, snapshots: list[FundamentalsSnapshot]) -> None:
        self._write_dataset(snapshots, "fundamentals")

    def _write_insider_transactions(self, transactions: list[InsiderTransaction]) -> None:
        self._write_dataset(transactions, "insider_transactions")

    def _write_mentions(self, mentions: list[MentionCount]) -> None:
        self._write_dataset(mentions, "mentions")

    def _read_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        return read_bars(self._analytical, self._base, symbol, start, end)

    # --- Port interface (Store) ---

    @override
    def save_bars(self, symbol: str, bars: list[Bar]) -> None:
        self._write_bars(bars)

    @override
    def load_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        return self._read_bars(symbol, start, end)

    # ---- State Store (DuckDB) ----

    SCHEMA_VERSION: int = 1

    def _init_state_schema(self) -> None:
        conn = self._state_conn
        conn.execute("CREATE TABLE IF NOT EXISTS schema_version (  version INTEGER NOT NULL)")
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        current_version = row[0] if row and row[0] else 0
        if current_version > 0 and current_version != self.SCHEMA_VERSION:
            logger.warning(
                "schema_version_mismatch",
                current=current_version,
                expected=self.SCHEMA_VERSION,
            )
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)",
            [self.SCHEMA_VERSION],
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS decisions ("
            "  decision_id VARCHAR,"
            "  run_id VARCHAR,"
            "  symbol VARCHAR NOT NULL,"
            "  decision_date DATE NOT NULL,"
            "  action VARCHAR NOT NULL,"
            "  confidence DOUBLE NOT NULL,"
            "  reasons JSON,"
            "  candidate_json JSON,"
            "  position_json JSON,"
            "  order_json JSON,"
            "  risk_results JSON,"
            "  mechanism_results JSON,"
            "  PRIMARY KEY (symbol, decision_date)"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS orders ("
            "  order_id VARCHAR PRIMARY KEY,"
            "  symbol VARCHAR NOT NULL,"
            "  action VARCHAR NOT NULL,"
            "  quantity DOUBLE NOT NULL,"
            "  order_type VARCHAR NOT NULL,"
            "  limit_price DOUBLE,"
            "  status VARCHAR NOT NULL,"
            "  submitted_at DATE,"
            "  fill_date DATE,"
            "  filled_quantity DOUBLE,"
            "  avg_fill_price DOUBLE"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS fills ("
            "  fill_id VARCHAR PRIMARY KEY,"
            "  order_id VARCHAR NOT NULL,"
            "  symbol VARCHAR NOT NULL,"
            "  quantity DOUBLE NOT NULL,"
            "  price DOUBLE NOT NULL,"
            "  filled_at TIMESTAMP NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS positions ("
            "  symbol VARCHAR PRIMARY KEY,"
            "  quantity DOUBLE NOT NULL,"
            "  entry_price DOUBLE,"
            "  avg_cost DOUBLE NOT NULL,"
            "  current_price DOUBLE,"
            "  stop_price DOUBLE,"
            "  trail_price DOUBLE,"
            "  market_value DOUBLE,"
            "  unrealized_pl DOUBLE,"
            "  realized_pl DOUBLE,"
            "  sector VARCHAR,"
            "  decision_id VARCHAR,"
            "  entry_date DATE,"
            "  high_since_entry DOUBLE,"
            "  partial_taken BOOLEAN NOT NULL DEFAULT FALSE"
            ")"
        )
        conn.execute("ALTER TABLE positions ADD COLUMN IF NOT EXISTS entry_date DATE")
        conn.execute("ALTER TABLE positions ADD COLUMN IF NOT EXISTS high_since_entry DOUBLE")
        conn.execute("ALTER TABLE positions ADD COLUMN IF NOT EXISTS partial_taken BOOLEAN")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS equity_curve ("
            "  equity_date DATE NOT NULL,"
            "  equity DOUBLE NOT NULL,"
            "  cash DOUBLE NOT NULL DEFAULT 0,"
            "  nav DOUBLE NOT NULL DEFAULT 0,"
            "  book VARCHAR NOT NULL DEFAULT 'PAPER',"
            "  PRIMARY KEY (equity_date, book)"
            ")"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_equity_curve_book "
            "ON equity_curve (book, equity_date DESC)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS events ("
            "  event_id VARCHAR PRIMARY KEY,"
            "  event_type VARCHAR NOT NULL,"
            "  timestamp TIMESTAMP NOT NULL,"
            "  run_id VARCHAR NOT NULL,"
            "  payload JSON NOT NULL"
            ")"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS concept_log ("
            "  log_id INTEGER PRIMARY KEY,"
            "  symbol VARCHAR,"
            "  concept VARCHAR NOT NULL,"
            "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
            "  meta JSON"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS indicator_state ("
            "  symbol VARCHAR NOT NULL,"
            "  state_date DATE NOT NULL,"
            "  values JSON NOT NULL,"
            "  status VARCHAR NOT NULL DEFAULT 'valid',"
            "  PRIMARY KEY (symbol, state_date)"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS catalog ("
            "  dataset VARCHAR NOT NULL,"
            "  version VARCHAR NOT NULL,"
            "  symbol VARCHAR NOT NULL,"
            "  coverage_start DATE,"
            "  coverage_end DATE,"
            "  row_count BIGINT,"
            "  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
            "  PRIMARY KEY (dataset, version, symbol)"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS quarantine ("
            "  symbol VARCHAR NOT NULL,"
            "  reason VARCHAR NOT NULL,"
            "  quarantined_date DATE NOT NULL,"
            "  cleared_date DATE,"
            "  severity VARCHAR NOT NULL DEFAULT 'QUARANTINE',"
            "  PRIMARY KEY (symbol, quarantined_date)"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS journal_entries ("
            "  entry_date DATE PRIMARY KEY,"
            "  content TEXT NOT NULL"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS reports ("
            "  report_date DATE NOT NULL,"
            "  report_type VARCHAR NOT NULL,"
            "  content TEXT NOT NULL,"
            "  PRIMARY KEY (report_date, report_type)"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS runs ("
            "  run_id VARCHAR PRIMARY KEY,"
            "  run_type VARCHAR NOT NULL,"
            "  config_hash VARCHAR NOT NULL,"
            "  fixture_version VARCHAR,"
            "  start_ts TIMESTAMP NOT NULL,"
            "  end_ts TIMESTAMP,"
            "  status VARCHAR NOT NULL DEFAULT 'running',"
            "  manifest_hash VARCHAR"
            ")"
        )
        conn.commit()

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

    @override
    def save_order(self, order: Order) -> None:
        self._state_conn.execute(
            "INSERT OR REPLACE INTO orders"
            " (order_id, symbol, action, quantity, order_type, limit_price, status,"
            "  submitted_at, fill_date, filled_quantity, avg_fill_price)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                order.order_id,
                order.symbol,
                order.action,
                order.quantity,
                order.order_type,
                order.limit_price,
                order.status,
                order.submitted_at,
                order.fill_date,
                order.filled_quantity,
                order.avg_fill_price,
            ],
        )

    @override
    def load_order(self, order_id: str) -> Order | None:
        row = self._state_conn.execute(
            "SELECT order_id, symbol, action, quantity, order_type, limit_price, status,"
            " submitted_at, fill_date, filled_quantity, avg_fill_price"
            " FROM orders WHERE order_id = ?",
            [order_id],
        ).fetchone()
        if row is None:
            return None
        return Order(
            order_id=row[0],
            symbol=row[1],
            action=row[2],
            quantity=row[3],
            order_type=row[4],
            limit_price=row[5],
            status=row[6],
            submitted_at=row[7],
            fill_date=row[8],
            filled_quantity=row[9],
            avg_fill_price=row[10],
        )

    @override
    def save_fill(self, fill: Fill) -> None:
        self._state_conn.execute(
            "INSERT OR REPLACE INTO fills"
            " (fill_id, order_id, symbol, quantity, price, filled_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            [
                fill.fill_id,
                fill.order_id,
                fill.symbol,
                fill.quantity,
                fill.price,
                fill.timestamp,
            ],
        )

    @override
    def load_fills(self, order_id: str) -> list[Fill]:
        rows = self._state_conn.execute(
            "SELECT fill_id, order_id, symbol, quantity, price, filled_at"
            " FROM fills WHERE order_id = ? ORDER BY filled_at",
            [order_id],
        ).fetchall()
        return [
            Fill(
                fill_id=r[0],
                order_id=r[1],
                symbol=r[2],
                quantity=r[3],
                price=r[4],
                timestamp=r[5],
            )
            for r in rows
        ]

    @override
    def save_position(self, position: Position) -> None:
        self._state_conn.execute(
            "INSERT OR REPLACE INTO positions"
            " (symbol, quantity, entry_price, avg_cost, current_price, stop_price, trail_price,"
            "  market_value, unrealized_pl, realized_pl, sector, decision_id,"
            "  entry_date, high_since_entry, partial_taken)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                position.symbol,
                position.quantity,
                position.entry_price,
                position.avg_cost,
                position.current_price,
                position.stop_price,
                position.trail_price,
                position.market_value,
                position.unrealized_pl,
                position.realized_pl,
                position.sector,
                position.decision_id,
                position.entry_date,
                position.high_since_entry,
                position.partial_taken,
            ],
        )

    @override
    def load_positions(self) -> list[Position]:
        cols = (
            "symbol, quantity, entry_price, avg_cost, current_price, stop_price, trail_price,"
            " market_value, unrealized_pl, realized_pl, sector, decision_id,"
            " entry_date, high_since_entry, partial_taken"
        )
        rows = self._state_conn.execute(f"SELECT {cols} FROM positions").fetchall()
        return [
            Position(
                symbol=r[0],
                quantity=r[1],
                entry_price=r[2],
                avg_cost=r[3],
                current_price=r[4],
                stop_price=r[5],
                trail_price=r[6],
                market_value=r[7],
                unrealized_pl=r[8],
                realized_pl=r[9],
                sector=r[10],
                decision_id=r[11],
                entry_date=r[12],
                high_since_entry=r[13],
                partial_taken=r[14],
            )
            for r in rows
        ]

    @override
    def save_event(self, event: DomainEvent) -> None:
        payload = event.model_dump(mode="json")
        self._state_conn.execute(
            "INSERT OR REPLACE INTO events"
            " (event_id, event_type, timestamp, run_id, payload)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                event.event_id,
                event.event_type,
                event.timestamp,
                event.run_id,
                json.dumps(payload),
            ],
        )

    @override
    def load_events(
        self,
        event_type: str | None = None,
        since: datetime | None = None,
    ) -> list[DomainEvent]:
        conditions: list[str] = []
        params: list[Any] = []
        if event_type is not None:
            conditions.append("event_type = ?")
            params.append(event_type)
        if since is not None:
            conditions.append("timestamp >= ?")
            params.append(since)

        where = " AND ".join(conditions) if conditions else "1=1"
        rows = self._state_conn.execute(
            f"SELECT payload FROM events WHERE {where} ORDER BY timestamp",
            params,
        ).fetchall()

        from alpha_quant.domain.events import DomainEvent as DomainEventType

        results: list[DomainEvent] = []
        for (payload_json,) in rows:
            payload = json.loads(payload_json)
            results.append(DomainEventType.model_validate(payload))
        return results

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

    @override
    def save_corp_actions(self, symbol: str, actions: list[CorporateAction]) -> None:
        self._write_dataset(actions, "corp_actions")

    @override
    def load_corp_actions(self, symbol: str) -> list[CorporateAction]:
        return load_corp_actions(self._analytical, self._base, symbol)

    @override
    def save_earnings(self, symbol: str, entries: list[EarningsEntry]) -> None:
        self._write_dataset(entries, "earnings")

    @override
    def load_earnings(self, symbol: str) -> list[EarningsEntry]:
        return load_earnings(self._analytical, self._base, symbol)

    @override
    def load_fundamentals(self, symbol: str) -> list[FundamentalsSnapshot]:
        return read_fundamentals(self._analytical, self._base, symbol)

    @override
    def load_insider_transactions(self, symbol: str) -> list[InsiderTransaction]:
        return read_insider_transactions(self._analytical, self._base, symbol)

    @override
    def load_mentions(self, symbol: str) -> list[MentionCount]:
        return read_mentions(self._analytical, self._base, symbol)

    @override
    def save_portfolio_snapshot(self, snapshot: PortfolioSnapshot) -> None:
        book = snapshot.book or "PAPER"
        self._state_conn.execute(
            "INSERT OR REPLACE INTO equity_curve"
            " (equity_date, equity, cash, nav, book)"
            " VALUES (?, ?, ?, ?, ?)",
            [snapshot.date, snapshot.equity, snapshot.cash, snapshot.equity, book],
        )

    @override
    def load_latest_portfolio_snapshot(self, book: str = "PAPER") -> PortfolioSnapshot | None:
        row = self._state_conn.execute(
            "SELECT equity_date, cash, equity FROM equity_curve"
            " WHERE book = ?"
            " ORDER BY equity_date DESC LIMIT 1",
            [book],
        ).fetchone()
        if row is None:
            return None
        return PortfolioSnapshot(date=row[0], cash=row[1], equity=row[2], book=book)

    @override
    def load_portfolio_snapshots(
        self, book: str = "PAPER", limit: int = 500
    ) -> list[PortfolioSnapshot]:
        rows = self._state_conn.execute(
            "SELECT equity_date, cash, equity FROM equity_curve"
            " WHERE book = ? ORDER BY equity_date ASC LIMIT ?",
            [book, limit],
        ).fetchall()
        return [PortfolioSnapshot(date=r[0], cash=r[1], equity=r[2], book=book) for r in rows]

    def add_quarantine(self, symbol: str, reason: str, severity: str = "QUARANTINE") -> None:
        self._state_conn.execute(
            "INSERT OR REPLACE INTO quarantine (symbol, reason, quarantined_date, severity)"
            " VALUES (?, ?, CURRENT_DATE, ?)",
            [symbol, reason, severity],
        )

    def list_quarantine(self, cleared: bool = False) -> list[dict[str, Any]]:
        if cleared:
            rows = self._state_conn.execute(
                "SELECT symbol, reason, quarantined_date, cleared_date, severity"
                " FROM quarantine WHERE cleared_date IS NOT NULL"
                " ORDER BY quarantined_date DESC"
            ).fetchall()
        else:
            rows = self._state_conn.execute(
                "SELECT symbol, reason, quarantined_date, cleared_date, severity"
                " FROM quarantine WHERE cleared_date IS NULL"
                " ORDER BY quarantined_date DESC"
            ).fetchall()
        return [
            {
                "symbol": r[0],
                "reason": r[1],
                "quarantined_date": str(r[2]),
                "cleared_date": str(r[3]) if r[3] else None,
                "severity": r[4],
            }
            for r in rows
        ]

    def clear_quarantine(self, symbol: str) -> None:
        self._state_conn.execute(
            "UPDATE quarantine SET cleared_date = CURRENT_DATE"
            " WHERE symbol = ? AND cleared_date IS NULL",
            [symbol],
        )

    def register_run(
        self,
        run_type: str,
        config_hash: str,
        fixture_version: str = "",
    ) -> str:
        run_id = uuid.uuid4().hex[:16]
        self._state_conn.execute(
            "INSERT INTO runs (run_id, run_type, config_hash, fixture_version, start_ts, status)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            [run_id, run_type, config_hash, fixture_version, datetime.now(UTC), "running"],
        )
        return run_id

    def complete_run(self, run_id: str, status: str = "completed", manifest_hash: str = "") -> None:
        self._state_conn.execute(
            "UPDATE runs SET end_ts = ?, status = ?, manifest_hash = ? WHERE run_id = ?",
            [datetime.now(UTC), status, manifest_hash, run_id],
        )

    def list_runs(self, since_date: date | None = None) -> list[dict[str, Any]]:
        if since_date is not None:
            rows = self._state_conn.execute(
                "SELECT run_id, run_type, config_hash, fixture_version,"
                " start_ts, end_ts, status, manifest_hash"
                " FROM runs WHERE start_ts >= ? ORDER BY start_ts DESC",
                [since_date],
            ).fetchall()
        else:
            rows = self._state_conn.execute(
                "SELECT run_id, run_type, config_hash, fixture_version,"
                " start_ts, end_ts, status, manifest_hash"
                " FROM runs ORDER BY start_ts DESC LIMIT 50"
            ).fetchall()
        return [
            {
                "run_id": r[0],
                "run_type": r[1],
                "config_hash": r[2],
                "fixture_version": r[3],
                "start_ts": str(r[4]),
                "end_ts": str(r[5]) if r[5] else None,
                "status": r[6],
                "manifest_hash": r[7],
            }
            for r in rows
        ]

    @override
    def save_journal(self, entry: JournalEntry) -> None:
        self._state_conn.execute(
            "INSERT OR REPLACE INTO journal_entries (entry_date, content) VALUES (?, ?)",
            [entry.date.isoformat(), entry.content],
        )

    @override
    def load_journal(self, dt: date) -> JournalEntry | None:
        row = self._state_conn.execute(
            "SELECT content FROM journal_entries WHERE entry_date = ?",
            [dt.isoformat()],
        ).fetchone()
        if row is None:
            return None
        return JournalEntry(date=dt, content=row[0])

    @override
    def save_report(self, report: ReportEntry) -> None:
        self._state_conn.execute(
            "INSERT OR REPLACE INTO reports (report_date, report_type, content) VALUES (?, ?, ?)",
            [report.date.isoformat(), report.report_type, report.content],
        )

    @override
    def load_report(self, dt: date, report_type: str) -> ReportEntry | None:
        row = self._state_conn.execute(
            "SELECT content FROM reports WHERE report_date = ? AND report_type = ?",
            [dt.isoformat(), report_type],
        ).fetchone()
        if row is None:
            return None
        return ReportEntry(
            date=dt,
            report_type=cast("ReportType", report_type),
            content=row[0],
        )

    def close(self) -> None:
        self._analytical.close()
        self._state_conn.close()

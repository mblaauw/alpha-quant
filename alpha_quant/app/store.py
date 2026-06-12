from __future__ import annotations

import json
import shutil
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Self, override

import duckdb
import pyarrow as pa
import structlog

from alpha_quant.domain.events import DomainEvent
from alpha_quant.domain.models import (
    Bar,
    Candidate,
    CorporateAction,
    Decision,
    Fill,
    FundamentalsSnapshot,
    IndicatorState,
    InsiderTransaction,
    MentionCount,
    Order,
    Position,
)
from alpha_quant.ports.store import Store

logger = structlog.get_logger()

_BAR_DATE_COL = "date"

_CANONICAL_SCHEMAS: dict[str, list[tuple[str, pa.DataType]]] = {
    "bars": [
        ("symbol", pa.string()),
        (_BAR_DATE_COL, pa.date32()),
        ("open", pa.float64()),
        ("high", pa.float64()),
        ("low", pa.float64()),
        ("close", pa.float64()),
        ("volume", pa.float64()),
        ("adj_close", pa.float64()),
    ],
    "fundamentals": [
        ("symbol", pa.string()),
        ("as_of_date", pa.date32()),
        ("market_cap", pa.float64()),
        ("pe_ratio", pa.float64()),
        ("eps_ttm", pa.float64()),
        ("dividend_yield", pa.float64()),
        ("sector", pa.string()),
        ("industry", pa.string()),
        ("operating_cash_flow", pa.float64()),
        ("total_debt", pa.float64()),
        ("total_equity", pa.float64()),
        ("revenue", pa.float64()),
        ("net_income", pa.float64()),
        ("accruals", pa.float64()),
    ],
    "insider_transactions": [
        ("symbol", pa.string()),
        ("filing_date", pa.date32()),
        ("transaction_date", pa.date32()),
        ("owner", pa.string()),
        ("title", pa.string()),
        ("transaction_type", pa.string()),
        ("shares_traded", pa.float64()),
        ("price", pa.float64()),
        ("shares_held", pa.float64()),
    ],
    "mentions": [
        ("symbol", pa.string()),
        ("mention_date", pa.date32()),
        ("source", pa.string()),
        ("count", pa.int64()),
    ],
    "corp_actions": [
        ("symbol", pa.string()),
        ("effective_date", pa.date32()),
        ("action_type", pa.string()),
        ("ratio", pa.float64()),
        ("amount", pa.float64()),
    ],
}


def _model_to_pylist(
    models: list[Any],
    model_name: str,
) -> list[dict[str, Any]]:
    match model_name:
        case "bars":
            return [
                {
                    "symbol": m.symbol,
                    _BAR_DATE_COL: m.date,
                    "open": m.open,
                    "high": m.high,
                    "low": m.low,
                    "close": m.close,
                    "volume": m.volume,
                    "adj_close": m.adj_close,
                }
                for m in models
            ]
        case "fundamentals":
            return [m.model_dump() for m in models] if models else []
        case "insider_transactions":
            return [
                {
                    "symbol": m.symbol,
                    "filing_date": m.filing_date,
                    "transaction_date": m.transaction_date,
                    "owner": m.owner,
                    "title": m.title,
                    "transaction_type": m.transaction_type,
                    "shares_traded": m.shares_traded,
                    "price": m.price,
                    "shares_held": m.shares_held,
                }
                for m in models
            ]
        case "mentions":
            return [
                {
                    "symbol": m.symbol,
                    "mention_date": m.date,
                    "source": m.source,
                    "count": m.count,
                }
                for m in models
            ]
        case "corp_actions":
            return [
                {
                    "symbol": m.symbol,
                    "effective_date": m.effective_date,
                    "action_type": m.action_type,
                    "ratio": m.ratio,
                    "amount": m.amount,
                }
                for m in models
            ]
        case _:
            return [m.model_dump() for m in models]


def _partition_col(model_name: str) -> str:
    mapping = {
        "bars": _BAR_DATE_COL,
        "fundamentals": "as_of_date",
        "insider_transactions": "filing_date",
        "mentions": "mention_date",
        "corp_actions": "effective_date",
    }
    return mapping.get(model_name, "date")


class CanonicalStore(Store):
    def __init__(self, base_path: str | Path) -> None:
        self._base = Path(base_path)
        self._base.mkdir(parents=True, exist_ok=True)

        self._analytical = duckdb.connect()
        self._analytical.execute("SET threads TO 1")

        self._state_path = self._base / "state.db"
        self._state_conn = duckdb.connect(str(self._state_path))
        self._state_conn.execute("PRAGMA journal_mode=WAL")
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
        if not models:
            return

        data_path = self._canonical_path(dataset)
        data_path.mkdir(parents=True, exist_ok=True)

        pylist = _model_to_pylist(models, dataset)
        new_table = pa.Table.from_pylist(pylist, schema=self._schema(dataset))

        pcol = _partition_col(dataset)
        dedup_key = _dedup_keys(dataset)
        hive_spec = f"hive_types={{'{pcol}': 'DATE'}}"

        # Find affected partition dates from new data
        new_dates = sorted(set(new_table.column(pcol).to_pylist()))
        if not new_dates:
            return

        min_date, max_date = min(new_dates), max(new_dates)

        # Find existing partition directories that overlap with new data
        affected_partitions: list[Path] = []
        for p_dir in data_path.iterdir():
            if not p_dir.is_dir() or not p_dir.name.startswith(f"{pcol}="):
                continue
            try:
                dt = date.fromisoformat(p_dir.name.split("=", 1)[1])
                if min_date <= dt <= max_date:
                    affected_partitions.append(p_dir)
            except ValueError, IndexError:
                continue

        self._analytical.register("_new_data", new_table)

        if not affected_partitions:
            # First write or no overlap with existing: write directly
            copy_opts = (
                f"FORMAT PARQUET, PER_THREAD_OUTPUT 1, PARTITION_BY {pcol}, COMPRESSION ZSTD"
            )
            self._analytical.execute(f"""
                COPY _new_data TO '{data_path}' ({copy_opts})
            """)
        else:
            # Read only affected partitions, merge with new data, write back
            file_patterns = [str(p / "*.parquet") for p in affected_partitions]
            read_parquet = (
                f"read_parquet([{', '.join(repr(f) for f in file_patterns)}],"
                f" hive_partitioning=true, {hive_spec})"
            )

            self._analytical.execute(f"""
                CREATE OR REPLACE TABLE _merged AS
                SELECT DISTINCT ON ({dedup_key}) *
                FROM (
                    SELECT * FROM {read_parquet}
                    UNION ALL
                    SELECT * FROM _new_data
                ) sub
                ORDER BY {dedup_key} DESC
            """)

            # Write merged data to a temp location first
            tmp_path = data_path.parent / f".tmp_{dataset}_{uuid.uuid4().hex[:8]}"
            tmp_path.mkdir(parents=True, exist_ok=True)

            copy_opts = (
                f"FORMAT PARQUET, PER_THREAD_OUTPUT 1, PARTITION_BY {pcol}, COMPRESSION ZSTD"
            )
            self._analytical.execute(f"""
                COPY (SELECT * FROM _merged ORDER BY {dedup_key})
                TO '{tmp_path}' ({copy_opts})
            """)

            self._analytical.execute("DROP TABLE IF EXISTS _merged")

            # Remove affected partitions from final location
            for p_dir in affected_partitions:
                shutil.rmtree(p_dir, ignore_errors=True)

            # Move merged partitions from temp to final
            for p_dir in tmp_path.iterdir():
                if p_dir.is_dir():
                    shutil.move(str(p_dir), str(data_path / p_dir.name))

            # Clean up temp directory
            shutil.rmtree(tmp_path, ignore_errors=True)

        self._analytical.unregister("_new_data")

        logger.debug(
            "store_write",
            dataset=dataset,
            count=len(models),
            partitions=len(affected_partitions),
        )

    def _schema(self, dataset: str) -> pa.Schema:
        fields = _CANONICAL_SCHEMAS[dataset]
        return pa.schema([pa.field(name, typ, nullable=typ != pa.date32()) for name, typ in fields])

    def write_bars(self, bars: list[Bar]) -> None:
        self._write_dataset(bars, "bars")

    def write_fundamentals(self, snapshots: list[FundamentalsSnapshot]) -> None:
        self._write_dataset(snapshots, "fundamentals")

    def write_insider_transactions(self, transactions: list[InsiderTransaction]) -> None:
        self._write_dataset(transactions, "insider_transactions")

    def write_mentions(self, mentions: list[MentionCount]) -> None:
        self._write_dataset(mentions, "mentions")

    def read_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        data_path = str(self._canonical_path("bars") / "**" / "*.parquet")
        pcol = _partition_col("bars")
        hive_spec = f"hive_types={{'{pcol}': 'DATE'}}"
        result = self._analytical.execute(
            f"""
            SELECT symbol, "{pcol}" AS date, open, high, low, close, volume, adj_close
            FROM read_parquet('{data_path}', hive_partitioning=true, {hive_spec})
            WHERE symbol = ? AND "{pcol}" >= ? AND "{pcol}" <= ?
            ORDER BY "{pcol}"
            """,
            [symbol, start, end],
        ).fetchall()

        return [
            Bar(
                symbol=r[0],
                date=r[1],
                open=r[2],
                high=r[3],
                low=r[4],
                close=r[5],
                volume=r[6],
                adj_close=r[7],
            )
            for r in result
        ]

    # --- Port interface (Store) ---

    @override
    def save_bars(self, symbol: str, bars: list[Bar]) -> None:
        self.write_bars(bars)

    @override
    def load_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        return self.read_bars(symbol, start, end)

    def prune(self, tail_days: int = 50) -> None:
        cutoff = date.today()
        for dataset in _CANONICAL_SCHEMAS:
            data_path = self._canonical_path(dataset)
            if not data_path.exists():
                continue
            pcol = _partition_col(dataset)
            removed = 0
            for partition_dir in sorted(data_path.iterdir()):
                if not partition_dir.is_dir() or not partition_dir.name.startswith(f"{pcol}="):
                    continue
                dt_str = partition_dir.name.split("=", 1)[1]
                try:
                    dt = date.fromisoformat(dt_str)
                except ValueError:
                    continue
                if (cutoff - dt).days > tail_days:
                    shutil.rmtree(partition_dir, ignore_errors=True)
                    removed += 1
            if removed:
                logger.info(
                    "store_prune",
                    dataset=dataset,
                    removed_partitions=removed,
                    tail_days=tail_days,
                )

    # ---- State Store (SQLite via DuckDB) ----

    def _init_state_schema(self) -> None:
        conn = self._state_conn
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
            "  decision_id VARCHAR"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS equity_curve ("
            "  equity_date DATE PRIMARY KEY,"
            "  equity DOUBLE NOT NULL,"
            "  cash DOUBLE NOT NULL DEFAULT 0,"
            "  nav DOUBLE NOT NULL DEFAULT 0"
            ")"
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
            "ALTER TABLE indicator_state ADD COLUMN IF NOT EXISTS status"
            " VARCHAR NOT NULL DEFAULT 'valid'"
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
        self._state_conn.commit()

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
        self._state_conn.commit()

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
        self._state_conn.commit()

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
            "  market_value, unrealized_pl, realized_pl, sector, decision_id)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
            ],
        )
        self._state_conn.commit()

    @override
    def load_positions(self) -> list[Position]:
        cols = (
            "symbol, quantity, entry_price, avg_cost, current_price, stop_price, trail_price,"
            " market_value, unrealized_pl, realized_pl, sector, decision_id"
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
        self._state_conn.commit()

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
        self._state_conn.commit()

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
        data_path = str(self._canonical_path("corp_actions") / "**" / "*.parquet")
        pcol = _partition_col("corp_actions")
        hive_spec = f"hive_types={{'{pcol}': 'DATE'}}"
        try:
            result = self._analytical.execute(
                f"""
                SELECT symbol, "{pcol}" AS effective_date, action_type, ratio, amount
                FROM read_parquet('{data_path}', hive_partitioning=true, {hive_spec})
                WHERE symbol = ?
                ORDER BY "{pcol}"
                """,
                [symbol],
            ).fetchall()
        except duckdb.CatalogException, duckdb.IOException:
            return []
        return [
            CorporateAction(
                symbol=r[0],
                effective_date=r[1],
                action_type=r[2],
                ratio=r[3],
                amount=r[4],
            )
            for r in result
        ]

    def add_quarantine(self, symbol: str, reason: str, severity: str = "QUARANTINE") -> None:
        self._state_conn.execute(
            "INSERT OR REPLACE INTO quarantine (symbol, reason, quarantined_date, severity)"
            " VALUES (?, ?, CURRENT_DATE, ?)",
            [symbol, reason, severity],
        )
        self._state_conn.commit()

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
        self._state_conn.commit()

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
            [run_id, run_type, config_hash, fixture_version, datetime.now(), "running"],
        )
        self._state_conn.commit()
        return run_id

    def complete_run(self, run_id: str, status: str = "completed", manifest_hash: str = "") -> None:
        self._state_conn.execute(
            "UPDATE runs SET end_ts = ?, status = ?, manifest_hash = ? WHERE run_id = ?",
            [datetime.now(), status, manifest_hash, run_id],
        )
        self._state_conn.commit()

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

    def close(self) -> None:
        self._analytical.close()
        self._state_conn.close()


def _dedup_keys(dataset: str) -> str:
    mapping = {
        "bars": "symbol, date",
        "fundamentals": "symbol, as_of_date",
        "insider_transactions": "symbol, filing_date, transaction_date, transaction_type, owner",
        "mentions": "symbol, mention_date, source",
        "corp_actions": "symbol, effective_date, action_type",
    }
    return mapping.get(dataset, "rowid")

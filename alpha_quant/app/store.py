from __future__ import annotations

import json
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import structlog

from alpha_quant.domain.events import DomainEvent
from alpha_quant.domain.models import (
    Bar,
    Decision,
    Fill,
    FundamentalsSnapshot,
    IndicatorState,
    InsiderTransaction,
    MentionCount,
    Order,
    Position,
)

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
}


def _model_to_pylist(
    models: list[Any],
    model_name: str,
) -> list[dict[str, Any]]:
    if model_name == "bars":
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
    if model_name == "fundamentals":
        return [m.model_dump() for m in models] if models else []
    if model_name == "insider_transactions":
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
    if model_name == "mentions":
        return [
            {
                "symbol": m.symbol,
                "mention_date": m.date,
                "source": m.source,
                "count": m.count,
            }
            for m in models
        ]
    return [m.model_dump() for m in models]


def _partition_col(model_name: str) -> str:
    mapping = {
        "bars": _BAR_DATE_COL,
        "fundamentals": "as_of_date",
        "insider_transactions": "filing_date",
        "mentions": "mention_date",
    }
    return mapping.get(model_name, "date")


class CanonicalStore:
    def __init__(self, base_path: str | Path) -> None:
        self._base = Path(base_path)
        self._base.mkdir(parents=True, exist_ok=True)

        self._analytical = duckdb.connect()
        self._analytical.execute("SET threads TO 1")

        self._state_path = self._base / "state.db"
        self._state_conn = duckdb.connect(str(self._state_path))
        self._state_conn.execute("PRAGMA journal_mode=WAL")
        self._init_state_schema()

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
        existing_pattern = str(data_path / "**" / "*.parquet")

        self._analytical.register("_new_data", new_table)

        dedup_key = _dedup_keys(dataset)
        hive_spec = f"hive_types={{'{pcol}': 'DATE'}}"
        read_parquet = f"read_parquet('{existing_pattern}', hive_partitioning=true, {hive_spec})"

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

        shutil.rmtree(data_path, ignore_errors=True)
        data_path.mkdir(parents=True, exist_ok=True)

        copy_opts = f"FORMAT PARQUET, PER_THREAD_OUTPUT 1, PARTITION_BY {pcol}, COMPRESSION ZSTD"
        self._analytical.execute(f"""
            COPY (SELECT * FROM _merged ORDER BY {dedup_key})
            TO '{data_path}' ({copy_opts})
        """)

        self._analytical.execute("DROP TABLE IF EXISTS _merged")
        self._analytical.unregister("_new_data")

        logger.debug(
            "store_write",
            dataset=dataset,
            count=len(models),
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
            "  symbol VARCHAR NOT NULL,"
            "  decision_date DATE NOT NULL,"
            "  action VARCHAR NOT NULL,"
            "  confidence DOUBLE NOT NULL,"
            "  reasons JSON,"
            "  PRIMARY KEY (symbol, decision_date)"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS orders ("
            "  order_id VARCHAR PRIMARY KEY,"
            "  symbol VARCHAR NOT NULL,"
            "  side VARCHAR NOT NULL,"
            "  quantity DOUBLE NOT NULL,"
            "  order_type VARCHAR NOT NULL,"
            "  limit_price DOUBLE,"
            "  status VARCHAR NOT NULL,"
            "  submitted_at TIMESTAMP,"
            "  filled_at TIMESTAMP,"
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
            "  avg_cost DOUBLE NOT NULL,"
            "  current_price DOUBLE,"
            "  market_value DOUBLE,"
            "  unrealized_pl DOUBLE,"
            "  realized_pl DOUBLE"
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
        conn.commit()

    def save_decision(self, decision: Decision) -> None:
        self._state_conn.execute(
            "INSERT OR REPLACE INTO decisions (symbol, decision_date, action, confidence, reasons)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                decision.symbol,
                decision.date,
                decision.action,
                decision.confidence,
                json.dumps(decision.reasons),
            ],
        )
        self._state_conn.commit()

    def load_decisions(self, symbol: str, since: date) -> list[Decision]:
        rows = self._state_conn.execute(
            "SELECT symbol, decision_date, action, confidence, reasons"
            " FROM decisions WHERE symbol = ? AND decision_date >= ?"
            " ORDER BY decision_date DESC",
            [symbol, since],
        ).fetchall()
        return [
            Decision(
                symbol=r[0],
                date=r[1],
                action=r[2],
                confidence=r[3],
                reasons=json.loads(r[4]) if r[4] else [],
            )
            for r in rows
        ]

    def save_order(self, order: Order) -> None:
        self._state_conn.execute(
            "INSERT OR REPLACE INTO orders"
            " (order_id, symbol, side, quantity, order_type, limit_price, status,"
            "  submitted_at, filled_at, filled_quantity, avg_fill_price)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                order.order_id,
                order.symbol,
                order.side,
                order.quantity,
                order.order_type,
                order.limit_price,
                order.status,
                order.submitted_at,
                order.filled_at,
                order.filled_quantity,
                order.avg_fill_price,
            ],
        )
        self._state_conn.commit()

    def load_order(self, order_id: str) -> Order | None:
        row = self._state_conn.execute(
            "SELECT order_id, symbol, side, quantity, order_type, limit_price, status,"
            " submitted_at, filled_at, filled_quantity, avg_fill_price"
            " FROM orders WHERE order_id = ?",
            [order_id],
        ).fetchone()
        if row is None:
            return None
        return Order(
            order_id=row[0],
            symbol=row[1],
            side=row[2],
            quantity=row[3],
            order_type=row[4],
            limit_price=row[5],
            status=row[6],
            submitted_at=row[7],
            filled_at=row[8],
            filled_quantity=row[9],
            avg_fill_price=row[10],
        )

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

    def save_position(self, position: Position) -> None:
        self._state_conn.execute(
            "INSERT OR REPLACE INTO positions"
            " (symbol, quantity, avg_cost, current_price, market_value, unrealized_pl, realized_pl)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                position.symbol,
                position.quantity,
                position.avg_cost,
                position.current_price,
                position.market_value,
                position.unrealized_pl,
                position.realized_pl,
            ],
        )
        self._state_conn.commit()

    def load_positions(self) -> list[Position]:
        cols = "symbol, quantity, avg_cost, current_price, market_value, unrealized_pl, realized_pl"
        rows = self._state_conn.execute(f"SELECT {cols} FROM positions").fetchall()
        return [
            Position(
                symbol=r[0],
                quantity=r[1],
                avg_cost=r[2],
                current_price=r[3],
                market_value=r[4],
                unrealized_pl=r[5],
                realized_pl=r[6],
            )
            for r in rows
        ]

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

    def save_indicator_state(self, state: IndicatorState) -> None:
        self._state_conn.execute(
            "INSERT OR REPLACE INTO indicator_state (symbol, state_date, values) VALUES (?, ?, ?)",
            [state.symbol, state.date, json.dumps(state.values)],
        )
        self._state_conn.commit()

    def load_indicator_state(self, symbol: str, dt: date) -> IndicatorState | None:
        row = self._state_conn.execute(
            "SELECT symbol, state_date, values"
            " FROM indicator_state WHERE symbol = ? AND state_date = ?",
            [symbol, dt],
        ).fetchone()
        if row is None:
            return None
        return IndicatorState(
            symbol=row[0],
            date=row[1],
            values=json.loads(row[2]),
        )

    def close(self) -> None:
        self._analytical.close()
        self._state_conn.close()


def _dedup_keys(dataset: str) -> str:
    mapping = {
        "bars": "symbol, bar_date",
        "fundamentals": "symbol, as_of_date",
        "insider_transactions": "symbol, filing_date, transaction_date, transaction_type, owner",
        "mentions": "symbol, mention_date, source",
    }
    return mapping.get(dataset, "rowid")

"""Canonical Parquet dataset operations.

Split from app/store.py — no behavior change.
"""

import shutil
import uuid
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import structlog

from alpha_quant.app.store.schema import dedup_keys, get_schema, model_to_pylist, partition_col
from alpha_quant.domain.models import (
    Bar,
    CorporateAction,
    EarningsEntry,
)

logger = structlog.get_logger()


def write_dataset(
    analytical: duckdb.DuckDBPyConnection,
    base: Path,
    models: list[Any],
    dataset: str,
) -> None:
    if not models:
        return

    data_path = base / "canonical" / dataset
    data_path.mkdir(parents=True, exist_ok=True)

    pylist = model_to_pylist(models, dataset)
    new_table = pa.Table.from_pylist(pylist, schema=get_schema(dataset))

    pcol = partition_col(dataset)
    dedup_key = dedup_keys(dataset)
    hive_spec = f"hive_types={{'{pcol}': 'DATE'}}"

    new_dates = sorted(set(new_table.column(pcol).to_pylist()))
    if not new_dates:
        return

    min_date, max_date = min(new_dates), max(new_dates)

    affected_partitions: list[Path] = []
    for p_dir in data_path.iterdir():
        if not p_dir.is_dir() or not p_dir.name.startswith(f"{pcol}="):
            continue
        try:
            dt = date.fromisoformat(p_dir.name.split("=", 1)[1])
            if min_date <= dt <= max_date:
                affected_partitions.append(p_dir)
        except (ValueError, IndexError):  # fmt: skip
            continue

    analytical.register("_new_data", new_table)

    if not affected_partitions:
        copy_opts = f"FORMAT PARQUET, PER_THREAD_OUTPUT 1, PARTITION_BY {pcol}, COMPRESSION ZSTD"
        analytical.execute(f"""
            COPY _new_data TO '{data_path}' ({copy_opts})
        """)
    else:
        file_patterns = [str(p / "*.parquet") for p in affected_partitions]
        read_parquet = (
            f"read_parquet([{', '.join(repr(f) for f in file_patterns)}],"
            f" hive_partitioning=true, {hive_spec})"
        )

        analytical.execute(f"""
            CREATE OR REPLACE TABLE _merged AS
            SELECT DISTINCT ON ({dedup_key}) *
            FROM (
                SELECT * FROM {read_parquet}
                UNION ALL
                SELECT * FROM _new_data
            ) sub
            ORDER BY {dedup_key} DESC
        """)

        tmp_path = data_path.parent / f".tmp_{dataset}_{uuid.uuid4().hex[:8]}"
        tmp_path.mkdir(parents=True, exist_ok=True)

        copy_opts = f"FORMAT PARQUET, PER_THREAD_OUTPUT 1, PARTITION_BY {pcol}, COMPRESSION ZSTD"
        analytical.execute(f"""
            COPY (SELECT * FROM _merged ORDER BY {dedup_key})
            TO '{tmp_path}' ({copy_opts})
        """)

        analytical.execute("DROP TABLE IF EXISTS _merged")

        for p_dir in tmp_path.iterdir():
            if not p_dir.is_dir():
                continue
            dest = data_path / p_dir.name
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            p_dir.rename(dest)

        shutil.rmtree(tmp_path, ignore_errors=True)

    analytical.unregister("_new_data")

    logger.debug(
        "store_write",
        dataset=dataset,
        count=len(models),
        partitions=len(affected_partitions),
    )


def read_bars(
    analytical: duckdb.DuckDBPyConnection, base: Path, symbol: str, start: date, end: date
) -> list[Bar]:
    data_path = str(base / "canonical" / "bars" / "**" / "*.parquet")
    pcol = partition_col("bars")
    dedup_key = dedup_keys("bars")
    hive_spec = f"hive_types={{'{pcol}': 'DATE'}}"
    result = analytical.execute(
        f"""
        SELECT DISTINCT ON ({dedup_key})
               symbol, "{pcol}" AS date, open, high, low, close, volume, adj_close
        FROM read_parquet('{data_path}', hive_partitioning=true, {hive_spec})
        WHERE symbol = ? AND "{pcol}" >= ? AND "{pcol}" <= ?
        ORDER BY {dedup_key} DESC
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


def load_corp_actions(
    analytical: duckdb.DuckDBPyConnection, base: Path, symbol: str
) -> list[CorporateAction]:
    data_path = str(base / "canonical" / "corp_actions" / "**" / "*.parquet")
    pcol = partition_col("corp_actions")
    hive_spec = f"hive_types={{'{pcol}': 'DATE'}}"
    try:
        result = analytical.execute(
            f"""
            SELECT symbol, "{pcol}" AS effective_date, action_type, ratio, amount
            FROM read_parquet('{data_path}', hive_partitioning=true, {hive_spec})
            WHERE symbol = ?
            ORDER BY "{pcol}"
            """,
            [symbol],
        ).fetchall()
    except (duckdb.CatalogException, duckdb.IOException):  # fmt: skip
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


def load_earnings(
    analytical: duckdb.DuckDBPyConnection, base: Path, symbol: str
) -> list[EarningsEntry]:
    data_path = str(base / "canonical" / "earnings" / "**" / "*.parquet")
    pcol = partition_col("earnings")
    hive_spec = f"hive_types={{'{pcol}': 'DATE'}}"
    try:
        result = analytical.execute(
            f"""
            SELECT symbol, "{pcol}" AS date, eps_estimate, eps_actual,
                   revenue_estimate, revenue_actual
            FROM read_parquet('{data_path}', hive_partitioning=true, {hive_spec})
            WHERE symbol = ?
            ORDER BY "{pcol}"
            """,
            [symbol],
        ).fetchall()
    except (duckdb.CatalogException, duckdb.IOException):  # fmt: skip
        return []
    return [
        EarningsEntry(
            symbol=r[0],
            date=r[1],
            eps_estimate=r[2],
            eps_actual=r[3],
            revenue_estimate=r[4],
            revenue_actual=r[5],
        )
        for r in result
    ]

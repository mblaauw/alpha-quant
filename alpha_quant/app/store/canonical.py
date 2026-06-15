"""Canonical Parquet dataset operations.

Split from app/store.py — no behavior change.
"""

import shutil
import uuid
from collections.abc import Callable
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
    FundamentalsSnapshot,
    InsiderTransaction,
    MentionCount,
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
        copy_opts = f"FORMAT PARQUET, PARTITION_BY {pcol}, COMPRESSION ZSTD"
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

        copy_opts = f"FORMAT PARQUET, PARTITION_BY {pcol}, COMPRESSION ZSTD"
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


def _read_dataset(
    analytical: duckdb.DuckDBPyConnection,
    base: Path,
    dataset: str,
    symbol: str,
    select_cols: str,
    model_factory: Callable[..., Any],
    order: str = "DESC",
) -> list[Any]:
    data_path = str(base / "canonical" / dataset / "**" / "*.parquet")
    pcol = partition_col(dataset)
    hive_spec = f"hive_types={{'{pcol}': 'DATE'}}"
    select = select_cols.replace("{pcol}", pcol)
    try:
        result = analytical.execute(
            f"SELECT {select} FROM read_parquet('{data_path}', hive_partitioning=true, {hive_spec})"
            f' WHERE symbol = ? ORDER BY "{pcol}" {order}',
            [symbol],
        ).fetchall()
    except (duckdb.CatalogException, duckdb.IOException):  # fmt: skip
        return []
    return [model_factory(*r) for r in result]


def read_bars(
    analytical: duckdb.DuckDBPyConnection, base: Path, symbol: str, start: date, end: date
) -> list[Bar]:
    data_path = str(base / "canonical" / "bars" / "**" / "*.parquet")
    pcol = partition_col("bars")
    dedup_key = dedup_keys("bars")
    hive_spec = f"hive_types={{'{pcol}': 'DATE'}}"
    try:
        result = analytical.execute(
            f"""
            SELECT DISTINCT ON ({dedup_key})
                   symbol, "{pcol}" AS date, open, high, low, close, volume, adj_close, fetch_id
            FROM read_parquet('{data_path}', hive_partitioning=true, {hive_spec})
            WHERE symbol = ? AND "{pcol}" >= ? AND "{pcol}" <= ?
            ORDER BY {dedup_key} DESC
            """,
            [symbol, start, end],
        ).fetchall()
    except (duckdb.CatalogException, duckdb.IOException):  # fmt: skip
        return []

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
            fetch_id=r[8],
        )
        for r in result
    ]


def load_corp_actions(
    analytical: duckdb.DuckDBPyConnection, base: Path, symbol: str
) -> list[CorporateAction]:
    return _read_dataset(
        analytical,
        base,
        "corp_actions",
        symbol,
        'symbol, "{pcol}" AS effective_date, action_type, ratio, amount, fetch_id',
        lambda *r: CorporateAction(
            symbol=r[0],
            effective_date=r[1],
            action_type=r[2],
            ratio=r[3],
            amount=r[4],
            fetch_id=r[5],
        ),
        order="ASC",
    )


def load_earnings(
    analytical: duckdb.DuckDBPyConnection, base: Path, symbol: str
) -> list[EarningsEntry]:
    return _read_dataset(
        analytical,
        base,
        "earnings",
        symbol,
        'symbol, "{pcol}" AS date,'
        " eps_estimate, eps_actual, revenue_estimate, revenue_actual, fetch_id",
        lambda *r: EarningsEntry(
            symbol=r[0],
            date=r[1],
            eps_estimate=r[2],
            eps_actual=r[3],
            revenue_estimate=r[4],
            revenue_actual=r[5],
            fetch_id=r[6],
        ),
        order="ASC",
    )


def read_fundamentals(
    analytical: duckdb.DuckDBPyConnection, base: Path, symbol: str
) -> list[FundamentalsSnapshot]:
    return _read_dataset(
        analytical,
        base,
        "fundamentals",
        symbol,
        'symbol, "{pcol}" AS as_of_date, market_cap, pe_ratio, eps_ttm,'
        " dividend_yield, sector, industry, operating_cash_flow,"
        " total_liabilities, total_debt, total_equity, revenue, net_income, accruals, fetch_id",
        lambda *r: FundamentalsSnapshot(
            symbol=r[0],
            as_of_date=r[1],
            market_cap=r[2],
            pe_ratio=r[3],
            eps_ttm=r[4],
            dividend_yield=r[5],
            sector=r[6],
            industry=r[7],
            operating_cash_flow=r[8],
            total_liabilities=r[9],
            total_debt=r[10],
            total_equity=r[11],
            revenue=r[12],
            net_income=r[13],
            accruals=r[14],
            fetch_id=r[15],
        ),
    )


def read_insider_transactions(
    analytical: duckdb.DuckDBPyConnection, base: Path, symbol: str
) -> list[InsiderTransaction]:
    return _read_dataset(
        analytical,
        base,
        "insider_transactions",
        symbol,
        'symbol, "{pcol}" AS filing_date, transaction_date, owner, title,'
        " transaction_type, shares_traded, price, shares_held, fetch_id",
        lambda *r: InsiderTransaction(
            symbol=r[0],
            filing_date=r[1],
            transaction_date=r[2],
            owner=r[3],
            title=r[4],
            transaction_type=r[5],
            shares_traded=r[6],
            price=r[7],
            shares_held=r[8],
            fetch_id=r[9],
        ),
    )


def read_mentions(
    analytical: duckdb.DuckDBPyConnection, base: Path, symbol: str
) -> list[MentionCount]:
    return _read_dataset(
        analytical,
        base,
        "mentions",
        symbol,
        'symbol, "{pcol}" AS mention_date, source, count, fetch_id',
        lambda *r: MentionCount(
            symbol=r[0], mention_date=r[1], source=r[2], count=r[3], fetch_id=r[4]
        ),
    )

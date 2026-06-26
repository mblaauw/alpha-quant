"""Generic CRUD helpers for DuckDB-backed store mixins."""

from __future__ import annotations

from typing import Any

import duckdb


def save_row(
    conn: duckdb.DuckDBPyConnection,
    table: str,
    columns: list[str],
    values: list[Any],
) -> None:
    cols = ", ".join(columns)
    placeholders = ", ".join("?" for _ in columns)
    conn.execute(f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})", values)


def load_one[T](
    conn: duckdb.DuckDBPyConnection,
    table: str,
    columns: list[str],
    model_cls: type[T],
    where: str = "1=1",
    params: list[Any] | None = None,
    order_by: str = "",
) -> T | None:
    cols = ", ".join(columns)
    order_clause = f" ORDER BY {order_by}" if order_by else ""
    row = conn.execute(
        f"SELECT {cols} FROM {table} WHERE {where}{order_clause}",
        params or [],
    ).fetchone()
    if row is None:
        return None
    return model_cls(**dict(zip(columns, row, strict=True)))  # type: ignore[call-overload]


def load_many[T](
    conn: duckdb.DuckDBPyConnection,
    table: str,
    columns: list[str],
    model_cls: type[T],
    where: str = "1=1",
    params: list[Any] | None = None,
    order_by: str = "",
    limit: int | None = None,
) -> list[T]:
    cols = ", ".join(columns)
    clauses = [f"SELECT {cols} FROM {table} WHERE {where}"]
    if order_by:
        clauses.append(f"ORDER BY {order_by}")
    if limit is not None:
        clauses.append(f"LIMIT {limit}")
    rows = conn.execute(" ".join(clauses), params or []).fetchall()
    return [model_cls(**dict(zip(columns, row, strict=True))) for row in rows]  # type: ignore[call-overload]

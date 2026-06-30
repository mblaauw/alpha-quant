# ADR-0061: DuckDB Retained for Legacy Import Only

## Status

Accepted

## Date

2026-06-30

## Context

DuckDB was the original analytical store and vault manifest database. PostgreSQL now serves as the sole operational store. DuckDB Parquet datasets still exist for historical data.

## Decision

DuckDB is retained solely for the db-import command that migrates legacy data into PostgreSQL. No new DuckDB writes. No analytical queries against DuckDB.

## Consequences

Positive:
- Single source of truth for the architecture.

Negative:
- None identified.


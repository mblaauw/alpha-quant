# ADR-0006: Use DuckDB + Parquet for the Analytical Store

## Status

Accepted

## Date

2026-06-10

## Context

Alpha-Quant needs to store and query analytical data: daily bars (OHLCV), fundamentals snapshots, insider transactions, and mention counts. Access patterns are columnar (scan a field across 50 symbols), date-partitioned (50-day tail), and append-mostly (new data daily).

DESIGN.md §3.4 specifies a split-store architecture: analytical data → Parquet/DuckDB, transactional state → DuckDB (per ADR-0021).

## Decision Drivers

- Columnar queries: "give me the close price for all symbols on date X" — a columnar format is 50-100x faster than row-based
- Date-partitioned pruning: dropping old data should be a directory delete, not a DELETE FROM table
- Zero server operations: the system runs on a single machine with no database server
- Append-only immutability: analytical data is written once, never modified
- Migration path: local parquet → S3/MinIO should be a non-event

## Considered Options

- **Option A: DuckDB + Parquet (date-partitioned)** — Columnar parquet files, queried via DuckDB with `read_parquet('.../**/*.parquet', hive_partitioning=true)`
- **Option B: SQLite only** — Single-file simplicity, but row-based storage is slow for columnar scans; no native partitioning
- **Option C: PostgreSQL** — Full-featured, but requires a server; overkill for single-machine deployment
- **Option D: pandas + pickle/npy files** — Simple but no query engine, no partitioning, no type safety

## Decision Outcome

Chosen option: **Option A — DuckDB + Parquet (date-partitioned)**.

Rationale:
1. DuckDB's columnar execution engine matches the access pattern perfectly: scanning 50 symbols × 1 field is a metadata-only operation on date-partitioned parquet
2. Date-partitioned pruning is a filesystem operation — `rm -rf canonical/bars/date=<old_date>/` is instant and safe
3. Zero server: DuckDB is an embedded database (same process), no daemon to manage
4. Parquet is the standard columnar format — the team already has PyArrow as a dependency
5. Migration path: change the DuckDB `read_parquet` path from local to S3 glob — nothing else changes

### Positive Consequences

- Columnar queries on 50 symbols × 3 years of daily bars execute in milliseconds
- The 50-day tail prune is a directory glob + delete — no heavy DELETE operations
- Parquet files are usable by any tool (Polars, pandas, Tableau) — no lock-in
- DuckDB reads parquet directly with zero ETL

### Negative Consequences

- Two storage systems to manage (DuckDB + Parquet) instead of one — but the access patterns justify it (DESIGN §3.4)
- Parquet files are not human-readable in a terminal (but DuckDB CLI can query them)
- DuckDB is not designed for concurrent writership (single-writer is fine for daily batch writes)

## References

- DESIGN.md §3.4 (Canonical store), §3.5 (Derived state), §3.8 (Library decisions)
- RAD §5 (Container Architecture — Parquet Archive), §6.1 (Data Layer Components)
- C4 Component diagram (Data Layer): `docs/architecture/views/data-layer-components.png`
- ADR-0007 (SQLite for transactional store)

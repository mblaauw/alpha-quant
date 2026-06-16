# ADR-0020: Use DuckDB for the Vault Manifest (Dual Use)

## Status

Accepted

## Date

2026-06-11

## Context

Alpha-Quant has two distinct storage needs for DuckDB:

1. **Analytical queries** (per ADR-0006): Columnar scans of date-partitioned Parquet files for indicators, scoring, and research — the primary use case documented in ADR-0006.
2. **Vault manifest** (P1.7): A content-addressable index of raw payloads — metadata tracking what has been fetched, compressed, and stored. This is an OLTP-like workload: row inserts, primary key lookups, filtered scans by source/date range.

The vault manifest could have been implemented in SQLite (which is already in the dependency list and more naturally suited for OLTP). However, using DuckDB for both purposes was chosen during implementation. This ADR documents the rationale for this dual-use decision.

## Decision Drivers

- **Single embedded database** — Avoid maintaining two database engines (DuckDB + SQLite) when one suffices
- **DuckDB WAL mode** — Concurrent access safety for vault writes (single writer, multiple readers — similar to SQLite WAL)
- **Simplified dependency tree** — If DuckDB can serve both roles, `sqlalchemy` can be deferred/removed (SQLite accessed via DuckDB's `sqlite` extension if needed)
- **Future query unification** — Querying vault metadata alongside analytical data in the same SQL dialect (e.g., "find all raw payloads for symbols that had a fundamentals update") without cross-database joins

## Considered Options

- **Option A: DuckDB for both manifest + analytical (current choice)** — Single embedded database, one query dialect, WAL mode for safety
- **Option B: SQLite for manifest, DuckDB for analytical** — Each database optimized for its workload; SQLite is more battle-tested for OLTP metadata
- **Option C: JSON manifest file** — Simple but not queryable, no schema enforcement, concurrent-safety issues

## Decision Outcome

Chosen option: **Option A — DuckDB for both manifest + analytical**.

Rationale:
1. DuckDB handles OLTP-light workloads well — the manifest receives ~100-500 inserts per daily run (one per API response) with primary-key lookups by fetch_id. This is not a high-volume OLTP workload that would expose DuckDB's row-level locking limitations.
2. The WAL mode (`PRAGMA wal_autocheckpoint='OFF'`) provides the same concurrent-reader safety as SQLite WAL during the daily pipeline.
3. Future convenience: querying vault metadata (e.g., "which sources have data for symbol X on date Y?") alongside analytical Parquet data in the same DuckDB session is seamless.
4. Simplifies the dependency footprint — avoids introducing SQLite as a second embedded database when DuckDB already covers both uses.

### Positive Consequences

- Single embedded database engine to understand and maintain
- Vault metadata queries reuse the same DuckDB connection as analytical queries
- DuckDB's SQL dialect (SQLite-compatible subset) means no new query language to learn

### Negative Consequences

- DuckDB is primarily an OLAP engine — it does not offer row-level locking or serialization isolation for true OLTP workloads. The manifest's ~500 row-inserts-per-day workload is well within DuckDB's comfort zone, but a future high-write scenario would require SQLite.
- DuckDB connection management is slightly more involved than sqlite3 (DuckDB connections are not lightweight for high-concurrency OLTP).
- If the manifest grows very large (millions of rows), DuckDB's lack of B-tree index support for single-row lookups might impact read performance — mitigated by content-addressable fetch_id lookups being hash-equality, not range scans.

## References

- ADR-0006: DuckDB + Parquet for the Analytical Store
- vault.py: `src/app/vault.py`
- P1.7: Raw vault implementation

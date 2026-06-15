# ADR-0021: Use DuckDB Directly for Both Analytical and Transactional State

## Status

Accepted

## Date

2026-06-11

## Context

Alpha-Quant originally planned (in ADR-0007) to use SQLite WAL via SQLAlchemy Core for transactional state (decisions, orders, fills, positions, events) and DuckDB + Parquet for analytical data (bars, fundamentals, insider transactions, mentions).

During P0/P1 implementation, the following emerged:

1. **SQLAlchemy Core was never used.** The `CanonicalStore` in `app/store/state.py` uses DuckDB for both analytical and transactional access — DuckDB's SQL and Parquet integration handle all tables directly.

2. **DuckDB supports both access patterns naturally.** It reads Parquet files for analytical scans and executes SQL against in-memory state tables for CRUD operations — no SQLAlchemy layer needed.

3. **The `sqlalchemy` dependency was already removed** from `pyproject.toml` during the P1.RB refactoring cleanup because it was never imported.

4. **DuckDB provides sufficient transactional guarantees** for the single-writer, daily-batch pipeline pattern. There is no concurrent write access, and the pipeline's ACID requirements are met by DuckDB's per-connection transaction semantics.

5. **Using one tool reduces complexity.** Eliminating SQLAlchemy Core removes a dependency, a configuration surface, and a potential source of type-mapping bugs between SQLAlchemy types and Pydantic model fields.

## Decision Drivers

- Actual implementation already uses DuckDB for everything — this ADR documents reality
- No concurrent write access needed (single-threaded daily pipeline)
- DuckDB's Parquet integration is essential for analytical queries
- Fewer dependencies = smaller lockfile, less audit surface
- Type safety: DuckDB + pyarrow + Pydantic provides end-to-end typed data flow

## Considered Options

- **Option A (current reality): DuckDB for everything** — One tool for both Parquet analytical store and SQLite-state-style CRUD. DuckDB handles both seamlessly.
- **Option B: Add SQLAlchemy Core back** — Re-introduce SQLAlchemy Core to wrap the transactional tables. Adds a dependency and abstraction layer with no benefit for the single-writer pattern.
- **Option C: Separate SQLite with raw sqlite3** — Use Python's built-in `sqlite3` module directly. This was roughly equivalent but adds a second query interface alongside DuckDB.

## Decision Outcome

Chosen option: **Option A — DuckDB for everything.**

Rationale:
1. The implementation already works with DuckDB for both access patterns
2. DuckDB's SQL covers everything needed: Parquet reads, transactional CRUD, and analytical window queries
3. No benefit to adding a second database interface for the single-writer pipeline

### Positive Consequences

- ADR-0007 is **Superseded** by this ADR
- `pyproject.toml` does not include `sqlalchemy` (already removed)
- Future migration to PostgreSQL for transactional state is still behind the `Store` port interface — DuckDB is an implementation detail
- Backup is: `cp` the DuckDB state file + rsync the Parquet partition directory

### Negative Consequences

- (None identified at this time)

## References

- ADR-0006 (DuckDB + Parquet for analytical store) — still active
- ADR-0007 (SQLite WAL + SQLAlchemy Core for transactional state) — superseded
- DESIGN.md §3.4 (Canonical store split by access pattern)
- `alpha_quant/app/store/state.py` — CanonicalStore implementation

# ADR-0007: Use SQLite WAL + SQLAlchemy Core for Transactional State

## Status

Accepted

## Date

2026-06-10

## Context

Alpha-Quant needs to persistently record decisions, orders, fills, positions, equity curves, events, indicator state, and catalog data — all transactionally. These are write-heavy during the daily pipeline (one transaction per fill batch), read-heavy for the narrator and dashboard. No concurrent write access needed (single-threaded pipeline).

DESIGN.md §3.4 splits state into analytical (Parquet/DuckDB) and transactional (SQLite).

## Decision Drivers

- ACID compliance: a crash in the middle of a fill batch must not corrupt the portfolio
- Single-file simplicity: backup is `cp state.db backup.db`
- Concurrent reads from the dashboard while the pipeline writes
- Schema migrations: the data model will evolve as mechanisms are added
- No database server to install or manage

## Considered Options

- **Option A: SQLite WAL via SQLAlchemy Core** — ACID, WAL mode allows reads during writes, SQLAlchemy Core provides typed SQL without ORM overhead
- **Option B: PostgreSQL** — Full-featured, but requires a server; overkill for single-machine local deployment
- **Option C: DuckDB for everything** — Great for analytical queries, but transactional guarantees (serialization isolation) are weaker; no row-level locking
- **Option D: JSON files on disk** — Simple but no ACID, no queryability, no schema enforcement

## Decision Outcome

Chosen option: **Option A — SQLite WAL via SQLAlchemy Core**.

Rationale:
1. SQLite WAL (Write-Ahead Logging) allows the Streamlit dashboard to read the database while the pipeline writes to it — no locking conflicts
2. SQLAlchemy Core (not ORM) provides parameterized SQL with type safety, without the overhead of ORM session management
3. Single file: `cp data/state.db backup/` is the entire backup — no pg_dump, no consistency checks
4. ACID compliance means a crash during `process_entry_orders` leaves the database in a consistent state (transaction rollback)
5. The access pattern is simple CRUD — no complex joins or recursive queries that would justify PostgreSQL

### Positive Consequences

- Backup is trivial (file copy, can be done hot with WAL mode)
- Dashboard reads never block pipeline writes (WAL mode)
- Schema migrations managed through SQLAlchemy Core DDL (explicit CREATE TABLE / ALTER TABLE in versioned migration scripts)
- Zero operational overhead — no server, no connection pooling

### Negative Consequences

- No concurrent write access (single-writer is fine for daily batch pipeline)
- SQLite does not support GRANT/REVOKE (not needed for local single-user deployment)
- Large databases (>10GB) require VACUUM (not expected for this scale — 50 symbols × daily data is ~100MB/year)

## References

- DESIGN.md §3.4 (Canonical store), §3.8 (Library decisions)
- RAD §5 (Container Architecture — SQLite State Store)
- C4 Container diagram: `docs/architecture/views/container.png`
- ADR-0006 (DuckDB + Parquet for analytical store)

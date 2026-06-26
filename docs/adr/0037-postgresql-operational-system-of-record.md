# ADR-0037: PostgreSQL as the Operational System of Record

**Status:** Accepted

**Date:** 2026-06-26

## Context

Alpha-Quant's production state management has evolved through three phases:

1. **P0–P1 (ADR-0007, ADR-0021):** SQLite WAL for transactional state, DuckDB for analytical state. Both were file-based local databases on the run host.

2. **P2–P3 (ADR-0006, ADR-0015):** DuckDB becomes both the analytical store and transactional state store. All positions, orders, fills, portfolio snapshots, and events live in a single `state.db` file.

3. **P4 (current):** The system has grown beyond what a single-node file database can support:
   - Multi-user operator dashboards need concurrent read access.
   - Audit trails require ACID guarantees across independent run sessions.
   - Historical replay benefits from time-travel queries and snapshot isolation.
   - S3 artifact store needs a durable, queryable metadata catalog.
   - Future FastAPI dashboard needs a server-side database with connection pooling.

DuckDB excels at analytical queries over large Parquet datasets, but Alpha-Quant's operational queries are transactional (single-row reads/writes on positions, orders, fills) rather than analytical.

## Decision

**PostgreSQL 17+ is the authoritative operational system of record for Alpha-Quant.**

DuckDB is removed from the production dependency chain. All state that was previously managed in DuckDB (`state.db`) is migrated to PostgreSQL tables managed via SQLAlchemy 2.0 Core + Alembic migrations.

### Scope

The PostgreSQL operational store covers:

- **Run lifecycle:** Decision runs, alpha-lake manifests, run locks
- **Paper trading:** Orders, fills, cash ledger entries, corporate actions
- **Portfolio state:** Current positions, portfolio marks, snapshot history
- **Audit trail:** Audit events, risk events, halt transitions
- **Operations:** Current halt state, run-lock audit

### Scope exclusions

- Market facts (bars, indicators, fundamentals) remain exclusively in Alpha-Lake.
- Decision evidence artifacts (JSON snapshots of each decision point) go to the S3 artifact store.
- Large analytical queries (backtest reports, portfolio analytics) may use DuckDB via an ephemeral query path for offline analysis only.

### Technology choices

- **Driver:** `psycopg` 3 with binary and pooling support
- **ORM:** SQLAlchemy 2.0 Core (not the ORM session pattern — explicit raw SQL via `text()`)
- **Migrations:** Alembic with versioned, repeatable migrations
- **Schema:** Six logical schemas (`core`, `run`, `trade`, `projection`, `audit`, `ops`) — not per-tenant. Multi-tenancy is a future concern.
- **Numeric type:** `NUMERIC(28,10)` for all monetary and quantity fields
- **Identifiers:** UUIDs stored as `VARCHAR(36)` for readability in queries

## Consequences

### Positive

- Server-grade concurrency — multiple operators can query positions simultaneously.
- ACID transactions across the full operational state.
- Time-travel via transaction snapshots and WAL archiving.
- Alembic provides structured, version-controlled schema migrations.
- Connection pooling via `psycopg_pool` eliminates file-lock contention.
- Well-known operational tooling (pgAdmin, DataGrip, `psql`).

### Negative

- Operational dependency on PostgreSQL server — local `state.db` required no server.
- Added deployment complexity: Docker container or managed PostgreSQL service.
- Schema management overhead — every model change requires an Alembic migration.
- `NUMERIC(28,10)` arithmetic in Python requires `Decimal` — no native `float` operations in domain logic.
- Testing requires either a PostgreSQL instance or a fake adapter for unit tests.

## Supersedes

- ADR-0007 (SQLite WAL + SQLAlchemy Core for transactional state)
- ADR-0021 (DuckDB for both analytical and transactional state)

## References

- ADR-0038 (Append-only ledger with rebuildable projections)
- ADR-0039 (S3-compatible artifact store)
- ADR-0041 (Migration strategy to `src/alpha_quant/`)
- `src/alpha_quant/adapters/postgres/`
- `src/alpha_quant/contracts/operational.py`

# ADR-0027: Dependency Pruning — polars, SQLAlchemy, APScheduler CLI, 50-Day Prune

## Status

Accepted

## Date

2026-06-13

## Context

During the P2 refinement cycle, four decisions were made that removed or changed earlier design assumptions. These were implemented across multiple PRs and refinement sprints but never documented as a formal ADR. This ADR captures the rationale for each change to maintain the decision record.

### 1. polars Removed from Dependencies

The original DESIGN.md §3.8 listed polars alongside DuckDB as a potential DataFrame library for analytical queries. In practice, ALL parquet reads go through DuckDB — polars was never imported anywhere in the codebase. DuckDB's SQL interface covers all analytical needs (equity curve queries, position reports, journal/report generation) without requiring a separate DataFrame library. The `polars` dependency was removed from `pyproject.toml` in P2.3.

### 2. SQLAlchemy Core Removed

ADR-0007 originally chose SQLite WAL via SQLAlchemy Core for transactional state. ADR-0021 later replaced this with DuckDB for both analytical and transactional state, rendering SQLAlchemy unnecessary. The transactional store rows are now managed via native DuckDB Python API (`duckdb.Connection.execute()`). All SQLAlchemy Core imports and `alembic` migration scaffolding were removed.

### 3. APScheduler CLI Removed

The original design included a `schedule` CLI subcommand that would start an APScheduler daemon. During P5.2 implementation, this was kept as an in-process BlockingScheduler. The CLI `schedule` subcommand exists but the original plan for apscheduler-based cron management was simplified to: schedule command starts the daemon; system-level cron handles daemon restart/health (see `docs/ops/CRON_FALLBACK.md`). The apscheduler dependency itself is retained for the scheduler daemon.

### 4. 50-Day Tail Prune Removed (P2.RO)

The original DESIGN.md §3.4 specified a 50-day rolling prune for the state store — keeping only the most recent 50 trading days of indicator state and positions. This was removed in P2.RO for several reasons:

1. **Vault replay dependency**: The golden replay CI strategy (ADR-0017) requires full historical data to verify determinism. Pruning breaks replay.
2. **Multi-timeframe indicators**: Some indicators (200-day EMA) require more than 50 days of history. Pruning makes them impossible to compute.
3. **Ablation analysis**: Shadow books need full history for comparison. Pruning destroys the ablatio n trail.
4. **Storage is cheap**: The state store is DuckDB, which compresses well. 10 years of daily data for 500 symbols is <100MB.

## Decision Drivers

- Minimize dependency surface area (fewer deps = fewer CVEs, less lockfile churn)
- Eliminate unused or superseded code paths
- Maintain backward compatibility for all active features
- Preserve full historical data for analysis and replay

## Considered Options

| Pruning Item | Option A: Keep | Option B: Remove | Outcome |
|---|---|---|---|
| polars | Keep unused dep, add CVE surface | **Remove** — never imported | **B: Remove** |
| SQLAlchemy | Keep for hypothetical future use | **Remove** — superseded by DuckDB | **B: Remove** |
| APScheduler CLI | Keep as-is | **Keep** — used by schedule command | **A: Keep** (dependency retained) |
| 50-day prune | Keep pruning logic | **Remove** — breaks replay/analysis | **B: Remove** |

## Decision Outcome

Remove polars and SQLAlchemy Core from project dependencies. Preserve APScheduler (the package) but simplify the integration strategy to in-process daemon + system cron. Remove all 50-day tail pruning logic from the state store.

### Positive Consequences

- Two fewer runtime dependencies (polars, sqlalchemy), reducing lockfile size and CVE surface
- Full historical data enables unbounded backtesting and ablation analysis
- Simpler storage model — no prune scheduling, no retention policy configuration
- SQLAlchemy migration scaffolding deleted (Alembic config, version table)

### Negative Consequences

- The state store will grow unboundedly. For long-running live deployments (>5 years), a separate purge/vacuum process may need to be designed.
- Removing SQLAlchemy means no ORM layer if the team wants to add a dashboard backend that uses SQLAlchemy models. However, the existing Streamlit dashboard reads DuckDB directly.
- If a future feature requires a full ORM (e.g., multi-user web backend), SQLAlchemy would need to be re-added.

## References

- ADR-0007: Use SQLite WAL + SQLAlchemy Core for Transactional State (superseded)
- ADR-0021: Use DuckDB for Both Analytical and Transactional State
- ADR-0017: Use Golden Replay as CI Strategy
- P2.RO commit: `11ccf87 store: Drop 50-day tail prune (P2.RO)`
- `docs/ops/CRON_FALLBACK.md`

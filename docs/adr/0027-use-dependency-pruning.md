# ADR-0027: Dependency Pruning & Tail Prune Removal

## Status

Accepted

## Date

2026-06-13

## Context

Since the initial scaffold (ADR-0020, ADR-0021), several dependencies and features have become redundant or were never actively used. Proactive dependency pruning reduces security surface, CI time, and cognitive overhead for new contributors.

Specific candidates for removal:

1. **Polars** — Added in P1.8 as a potential faster alternative to DuckDB for analytical queries. All analytical reads go through DuckDB's `read_parquet`; Polars is never imported in any source file (`git grep polars` returns zero results outside `pyproject.toml`).
2. **SQLAlchemy** — Originally used for SQLite transactional state (ADR-0007). Superseded by DuckDB for transactional state (ADR-0021) and removed from imports but lingered in `pyproject.toml`.
3. **APScheduler CLI** — The `schedule` subcommand was originally designed to run as a daemon. In practice, system cron (via `CRON_FALLBACK.md`) is more reliable and simpler to monitor. The APScheduler library remains as a dependency for the scheduler module, but the CLI entry point is pruned.
4. **50-day tail prune** — The `CanonicalStore` had a 50-day tail prune that automatically deleted old partitions. The P2.RO spike found this was never triggered (fixtures never exceed 50 days; live runs keep data for backtesting). Removed entirely.

## Decision Drivers

- Reduce CI install time and dependency audit surface
- Remove dead code paths that are never exercised
- Align `pyproject.toml` with actual imports (`git grep` verification)

## Considered Options

- **Do nothing** — Dead dependencies add ~200ms to `uv sync` and increase Dependabot noise
- **Remove aggressively** — Could break if any code path transitively depends on these

## Decision Outcome

Prune the following from `pyproject.toml`:
- `polars` (never imported)
- `sqlalchemy` (superseded by DuckDB)
- `apscheduler` → retained as main dependency (scheduler is a core application feature, not optional)

The 50-day tail prune code is removed from `CanonicalStore._write_dataset`.

Dependency pruning was deferred until now because during active development (P0–P2), the marginal cost of extra dependencies was negligible. Now that the system is in refinement, pruning is worthwhile.

### Positive Consequences

- Faster `uv sync` (~200ms saved)
- Smaller SBOM for security scanning
- Dead code paths removed (tail prune)

### Negative Consequences

- (none — apscheduler retained as main dependency)

## References

- ADR-0007 (SQLite + SQLAlchemy) — superseded by ADR-0021
- ADR-0021 (DuckDB for transactional state)
- DESIGN.md §3.4 (Canonical store)

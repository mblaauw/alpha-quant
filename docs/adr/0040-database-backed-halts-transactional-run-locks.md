# ADR-0040: Database-Backed Halts and Transactional Run Locks

**Status:** Accepted

**Date:** 2026-06-26

## Context

Alpha-Quant's halt mechanism (ADR-0031) was file-based: the system writes a file to indicate a halted state, and reads it at the start of each decision cycle to check whether to proceed. This worked for a single-process system but has several limitations:

1. **No atomicity**: Writing and reading the halt file is not atomic across processes.
2. **No concurrency prevention**: Nothing prevents two decision runs from starting simultaneously — a serious issue when the system transitions to a server-based architecture with operator-triggered runs.
3. **No history**: File-based halts leave no audit trail of when and why the halt was set or cleared.
4. **No time-to-live**: A halt set by one process persists until explicitly cleared, even if the process crashed.
5. **Process coupling**: The halt file lives on the local filesystem — multi-node deployments cannot share halt state.

## Decision

**Replace the file-based halt mechanism with database-backed halts and PostgreSQL advisory locks for concurrent run prevention.**

### Halt state

The `ops.current_halt` table stores the current halt state:

| Column | Type | Description |
|--------|------|-------------|
| `halt_id` | `UUID` | Unique halt identifier |
| `halted` | `BOOLEAN` | Whether the system is halted |
| `reason` | `VARCHAR` | Human-readable reason |
| `set_at` | `TIMESTAMPTZ` | When the halt was set |
| `source` | `VARCHAR` | What set the halt (pipeline, CLI, operator) |

Halt transitions are recorded in `audit.halt_transition` for the audit trail.

### Concurrent run prevention

Before starting a decision run, the system acquires a PostgreSQL advisory lock with a well-known key (e.g., `hash('alpha-quant-run')`). If the lock cannot be acquired, the run is aborted with a "concurrent run detected" error.

This approach:

- Works across connections and processes.
- Automatically releases on connection drop (no orphaned locks).
- Requires no external coordination service.
- Is explicitly scoped to the database server — multiple database instances are not expected.

### CLI integration

The existing CLI `halt` and `unhalt` commands are preserved, but their implementation switches from file I/O to database SQL:

- `alpha-quant halt "reason"` → `INSERT INTO ops.current_halt (...)`
- `alpha-quant unhalt` → `DELETE FROM ops.current_halt`
- `alpha-quant status` → `SELECT * FROM ops.current_halt`
- `alpha-quant db-health` → Verifies the database is reachable and not halted.

### Migration

The old file-based halt (`state.halt`) is removed. No migration path is needed for the halt state — it is transient state that can be safely discarded.

## Consequences

### Positive

- Atomic halt check/clear via database transactions.
- Audit trail of every halt transition.
- No orphaned locks (PostgreSQL releases advisory locks on connection close).
- Multi-process safe — concurrent runs are prevented at the database level.
- Works across container restarts (halt state survives in PostgreSQL).

### Negative

- Halt depends on database availability — if the database is unreachable, halt state is unknowable.
- Advisory locks are PostgreSQL-specific — not portable to other databases.
- Lock key collision is possible (mitigated by using a well-known hash).

## Supersedes

- ADR-0031 (File-based halt mechanism)

## References

- ADR-0037 (PostgreSQL operational system of record)
- ADR-0038 (Append-only ledger with rebuildable projections)
- `src/alpha_quant/adapters/postgres/operational_store.py`
- `src/alpha_quant/contracts/operational.py`

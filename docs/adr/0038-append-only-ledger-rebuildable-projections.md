# ADR-0038: Append-Only Operational Ledger with Rebuildable Projections

**Status:** Accepted

**Date:** 2026-06-26

## Context

Paper trading and portfolio management require both the authoritative record of every action (the ledger) and fast access to current state (the projection). A common approach is full event sourcing — storing every domain event as the single source of truth and rebuilding projections by replaying the event stream.

However, full event sourcing introduces operational complexity that is disproportionate for Alpha-Quant's scale:

- Event replay must be deterministic and ordered across multiple aggregate types.
- Snapshotting is needed to avoid replaying the entire history on every read.
- Events must be versioned and backward-compatible indefinitely.
- The schema migration story for events is harder than for tables.

Alpha-Quant's requirements are less demanding: the system processes one decision cycle per trading day, produces O(10–100) events per cycle, and the projection state (positions, portfolio marks) changes incrementally.

## Decision

**Use an append-only operational ledger stored in PostgreSQL tables, with separate projection tables that are rebuilt from the ledger during startup and on demand.**

This is not full event sourcing. The approach is:

### Ledger tables (append-only)

- `audit.audit_event` — one row per domain event. Immutable after insert.
- `trade.cash_ledger_entry` — one row per cash movement. Immutable after insert.
- `trade.corporate_action_booking` — one row per corporate action. Immutable after insert.
- `trade.paper_order` — contains order lifecycle. Status may transition, but order creation is append-only.
- `trade.paper_fill` — one row per fill. Immutable after insert.

### Projection tables (idempotent, rebuildable)

- `projection.position_current` — current open positions. Rebuilt by replaying fills from `trade.paper_fill`.
- `projection.portfolio_current` — current cash/equity/regime snapshot. Rebuilt by replaying ledger entries.

### Recovery procedure

On startup, if projection tables are empty or stale (checked via ledger watermark), the system:

1. Reads all ledger entries since the last known projection mark.
2. Recomputes `position_current` and `portfolio_current`.
3. Writes the projection rows using `INSERT ... ON CONFLICT REPLACE`.

This is not a full replay of the event stream — only the projection-relevant subset of tables is replayed.

### Why not full event sourcing

| Concern | Full event sourcing | This approach |
|---------|-------------------|---------------|
| Write path | Append to event store only | Append to ledger + upsert projections |
| Read path | Replay events + apply snapshots | Direct SQL read from projection tables |
| Schema evolution | Versioned events, upcasting | Alembic migrations on tables |
| Complexity | High (event store, snapshots, upcasters) | Low (standard SQL patterns) |
| Determinism | Requires careful ordering | Idempotent upserts are ordering-tolerant |
| Audit trail | Built-in (events are the source of truth) | Separate audit_event table |

## Consequences

### Positive

- Current state reads are fast (direct table lookup, not event replay).
- Recovery is simple (replay limited set of ledger tables).
- Alembic handles schema evolution without event versioning.
- Standard SQL patterns — no event store infrastructure.
- Audit trail is a regular table, queryable with SQL.

### Negative

- Two representations of truth (ledger + projection) can drift if the rebuild logic has a bug.
- Rebuild requires careful ordering — fills must be replayed in chronological order.
- Not a pure event-sourced system — some state changes are not captured as domain events (e.g., position mark-to-market).
- The rebuild procedure must be tested and verified against the ledger.

## References

- ADR-0037 (PostgreSQL operational system of record)
- ADR-0039 (S3-compatible artifact store)
- `src/alpha_quant/adapters/postgres/operational_store.py`
- `src/alpha_quant/contracts/operational.py`

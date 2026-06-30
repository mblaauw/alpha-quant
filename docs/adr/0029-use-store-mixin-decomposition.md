# ADR-0029: Use Store Mixin Decomposition for Schema Organization

## Status

Superseded by ADR-0044 (OperationalStore).

## Date

2026-06-15

## Context

The canonical store manages two distinct storage backends: DuckDB for transactional state (state.db) and Parquet-for-DuckDB for analytical data (bars, fundamentals, insider transactions). Early versions had a single `CanonicalStore` class with all 19+ methods in one file (~600 lines), making it difficult to navigate, test, and maintain.

Each storage concern has different schema, access patterns, and lifecycle:
- **State tables** (`positions`, `decisions`, `orders`, `events`, `equity_curve`, `runs`, `quarantine`, `journal_entries`, `reports`) — row-level CRUD with DuckDB
- **Analytical datasets** (`bars`, `fundamentals`, `insider_transactions`, `mentions`, `corp_actions`, `earnings`) — Parquet partition writes with DuckDB reads
- **Admin tables** (`schema_version`, `catalog`, `indicator_state`) — mixed read/write patterns

## Decision Drivers

- **Navigability** — Each file should contain one clear concern (< 100 lines)
- **Testability** — Mixin methods can be tested in isolation with focused fixtures
- **Single responsibility** — Schema definition, bar I/O, decision persistence, and event storage have different change rates
- **Backward compatibility** — External callers import from `app.store` and get the composed `CanonicalStore` — mixin structure is an internal detail

## Considered Options

- **Option A: Mixin classes (current choice)** — `CanonicalStore` inherits from 9 specialized mixins, each in its own file under `app/store/`. The mixins share the same database connection via `self._state_conn` and `self._canonical_conn`
- **Option B: Single monolithic class** — One file, 600+ lines. Simple but hard to navigate
- **Option C: Composition over inheritance** — `CanonicalStore` contains separate `PositionStore`, `EventStore`, etc. as attributes. Each has its own connection
- **Option D: Module-level functions** — No class at all; functions accept a connection parameter

## Decision Outcome

Chosen option: **Option A — Mixin classes**.

Rationale:
1. Each mixin is a focused 20-60 line file with a single concern
2. Mixins share the database connections from `CanonicalStore.__init__()` — no connection overhead
3. External import paths are clean: `from app.store import CanonicalStore`
4. Composition (Option C) would require each sub-store to manage its own connection or accept one — extra wiring
5. Module-level functions (Option D) would lose the natural grouping of state mutations under a single lifecycle

### Positive Consequences

- Store code is organized by domain concept, not by persistence layer
- Adding a new dataset requires only a new mixin file and a parent class addition
- Mixins can be unit-tested with a DuckDB `:memory:` connection
- Schema definitions are centralized in `app/store/schema.py`, shared by all mixins

### Negative Consequences

- Python MRO requires care — mixin `__init__` methods must call `super().__init__()` or be avoided
- Some column-name duplication exists between mixins (INSERT/SELECT column lists) — tracked as P2.14 in the refactoring punch list
- New contributors must understand the mixin pattern

## References

- `src/app/store/__init__.py` — re-exports `CanonicalStore`
- `src/app/store/state.py` — schema initialization
- `src/app/store/position_store.py`, `event_store.py`, `decision_store.py`, `order_store.py`, `bar_store.py`, `admin_store.py`, `journal_store.py`, `indicator_store.py`, `canonical.py`

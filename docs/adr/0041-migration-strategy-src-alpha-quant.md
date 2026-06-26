# ADR-0041: Migration Strategy — Consolidating to `src/alpha_quant/`

**Status:** Accepted

**Date:** 2026-06-26

## Context

The codebase has evolved through multiple architectural phases, each leaving its source files in a different root:

| Root | Origin | Contents |
|------|--------|---------|
| `src/domain/` | P0 monolith | Core domain models, risk, fills, sizing, ranking, events, invariants |
| `src/ports/` | P2 ports extraction | Store port, clock port, event sink, LLM port |
| `src/adapters/` | P2 adapters extraction | Fake store, real store (DuckDB), fake clock, real clock, LLM adapters |
| `src/app/` | P1-P3 app layer | Pipeline, CLI, dashboard, config, factory, store mixins, halt mechanism |
| `src/alpha_quant/` | P4 new architecture | Contracts, ports, domain/policy, adapters (Postgres, S3, Alpha-Lake), application factory, migrations |

This multi-root layout creates several problems:

1. **Import confusion**: Files in `src/app/` import from both `alpha_quant.*` and `domain.*` — two parallel representations of the same concepts.
2. **No clear boundary**: Legacy files in `src/domain/` contain the core trading logic (risk, sizing, fills) that the new `alpha_quant.*` code depends on.
3. **Dead code risk**: It's unclear which legacy files are still active and which are vestigial.
4. **Tooling complexity**: `ruff` and `ty` must be configured to check multiple source roots.
5. **Mental model**: Developers must know which root to put new code in.

## Decision

**Consolidate all live code into `src/alpha_quant/` and delete the legacy roots (`src/domain/`, `src/ports/`, `src/adapters/`, `src/app/`).**

### Target directory structure

```
src/alpha_quant/
├── __init__.py              # Public API exports
├── application/             # Composition root, factory, CLI, dashboard
│   ├── factory.py
│   ├── dashboard/           # Future FastAPI dashboard
│   └── cli.py               # CLI entrypoint
├── contracts/               # Shared data contracts (frozen dataclasses)
│   ├── alpha_lake.py
│   └── operational.py
├── domain/                  # Domain logic
│   ├── decision_context.py
│   └── policy/              # Policy modules (7 modules)
├── ports/                   # Protocol interfaces
│   ├── alpha_lake.py
│   ├── artifact_store.py
│   └── operational_store.py
├── adapters/                # Concrete implementations
│   ├── _parse.py            # Shared parsing helpers
│   ├── postgres/            # PostgreSQL operational store
│   ├── artifacts/           # S3 artifact store
│   ├── real/                # Real Alpha-Lake REST client
│   └── fake/                # Fake Alpha-Lake fixture client
└── migrations/              # Alembic migrations
```

### Migration phases

| Phase | Action | Status |
|-------|--------|--------|
| 5a | Move `src/domain/` → `src/alpha_quant/domain/` (legacy domain logic) | Pending |
| 5b | Move `src/ports/` → `src/alpha_quant/ports/` (legacy ports) | Pending |
| 5c | Move `src/adapters/` → `src/alpha_quant/adapters/` (legacy adapters) | Pending |
| 5d | Move `src/app/` → `src/alpha_quant/application/` (app layer) | Pending |
| 5e | Delete legacy roots; update `pyproject.toml` | Pending |

### What stays in `src/alpha_quant/` after consolidation

- All domain logic — risk, sizing, fills, ranking, events, invariants, models
- All port interfaces — store, clock, event sink, LLM
- All adapter implementations — PostgreSQL, S3, DuckDB (for legacy data import), Alpha-Lake, fake variants
- Application layer — CLI, factory, pipeli`ne_v2.py, config
- Migrations — Alembic
- Contracts — alpha_lake, operational

### What gets deleted

- Legacy `src/domain/`, `src/ports/`, `src/adapters/`, `src/app/` directories
- Dead concepts from legacy domain that have no counterpart in Phase 4+:
  - `src/domain/ask.py` (LLM-based question answering — not used in pipeline)
  - `src/app/scheduler.py` (APScheduler — not wired to new pipeline)

### What stays in place (already in `src/alpha_quant/`)

- All Phase 4 code: contracts, neutral observation types, policy modules, PostgreSQL adapters, S3 adapters, Alpha-Lake adapters, decision context, migrations, application factory.

## Consequences

### Positive

- Single source root — no ambiguity about where new code goes.
- Clear namespace — `alpha_quant.*` is the only Python package.
- Tooling simplified — single `src/alpha_quant/` path for linting and type checking.
- Dead code visibility — anything that can't be moved is genuinely unused.
- Backward compatibility during migration — imports are updated file by file.

### Negative

- Large single commit when the move actually happens.
- All PRs from the migration period create merge conflicts.
- Internal imports must be rewritten (`from domain.*` → `from alpha_quant.domain.*`).
- The move requires coordination with any open feature branches.
- `src/alpha_quant/__init__.py` must be updated to export a stable public API.

## References

- ADR-0037 (PostgreSQL operational system of record)
- ADR-0040 (Database-backed halts)
- `src/alpha_quant/`
- `pyproject.toml` (build configuration)

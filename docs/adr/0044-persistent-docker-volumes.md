# ADR-0044: Persistent Named Docker Volumes and Idempotent Migrations

## Status

Accepted

## Date

2026-06-26

## Context

Alpha-Quant runs as a multi-service Docker Compose stack in production. The stack includes PostgreSQL, an S3-compatible artifact store, a FastAPI server, and a command worker.

Operational data (books, decisions, orders, fills, journal entries, decision evidence) must survive container restarts, rebuilds, and deployment updates. Schema changes must be applied forward-only and idempotently.

Normal Docker operations (`up`, `down`, `restart`, `up --build`) must never lose data. Data deletion must require an explicit, confirmed destructive command.

## Options Considered

1. **Host-mounted volumes** — simple but path-dependent, not portable across hosts
2. **Anonymous volumes** — created by Docker but not easily referenced or backed up
3. **Named persistent volumes** — explicitly created, portable, referenceable, survive container lifecycle
4. **Ephemeral containers without volumes** — data loss on every restart

## Decision

Use named persistent Docker volumes for all stateful services.

- `alpha_quant_pgdata` — PostgreSQL data directory
- `alpha_quant_artifacts` — S3-compatible artifact store data

The compose stack ensures safe startup ordering:

```
postgres (healthy) -> migrate (completed) -> api + worker
artifacts (healthy) -> artifact-init (completed) -> api + worker
```

- `migrate` runs Alembic migrations forward-only, idempotently
- `artifact-init` creates the `alpha-quant-artifacts` bucket only when absent
- No application startup path drops, truncates, recreates, or seeds operational data

## Consequences

**Positive:**

- `docker compose up -d`, `down`, `restart`, and `up --build` preserve all data
- Migrations are forward-only and idempotent — already-applied migrations are harmless
- Explicit destructive reset commands (`just reset-db`, `just reset-artifacts`, `just reset-all`) require confirmation tokens

**Negative:**

- Named volumes must be explicitly removed with `docker volume rm` to reclaim disk space
- Backup/restore requires separate tooling (the justfile provides `db-backup` and `db-restore` recipes)

## Related

- ADR-0037 (PostgreSQL Operational System of Record)
- ADR-0039 (S3-Compatible Artifact Store)

# ADR-0048: Commands Are the Sole Mutation Boundary

## Status

Accepted

## Date

2026-06-27

## Context

Early Alpha-Quant dashboard routes performed direct state mutations — writing to DuckDB, managing halt files, and manipulating portfolio state inline. This created safety problems:

1. **No audit trail** — mutations happened without recording who, why, or when
2. **No idempotency** — retrying a request could duplicate state changes
3. **No conflict detection** — concurrent operators could overwrite each other's changes
4. **No worker coordination** — the decision pipeline had no visibility into pending mutations

The durable command model (ADR-0043) introduced a command queue with idempotency, version checks, and audit logging. All operator-initiated mutations should flow through this model exclusively.

## Decision Drivers

- **Auditability** — every mutation must record operator identity, reason, and timestamp
- **Idempotency** — retrying a command must not duplicate state changes
- **Conflict detection** — expected-version checks prevent lost updates
- **Worker coordination** — the pipeline worker claims and executes commands atomically

## Decision Outcome

All operator writes are durable, idempotent, audited commands handled through the application layer and worker.

The following routes are the only mutation endpoints:

```text
POST /v1/commands           → submit command
GET  /v1/commands           → list commands
GET  /v1/commands/{id}      → poll command status
POST /v1/commands/{id}/cancel → cancel pending command
```

### Read-only routes

```text
GET /v1/console/*           → operational read models (never mutate)
GET /livez                  → health check
GET /readyz                 → readiness check
```

### Forbidden patterns

```text
No dashboard route performs direct state mutation.
No browser-side SQL, DuckDB, or PostgreSQL access.
No file-based halt read/write from the GUI.
No direct portfolio state manipulation through read endpoints.
No command auto-retry on the frontend.
```

## Consequences

### Positive

- Every mutation has an audit record with operator identity
- Idempotency keys prevent duplicate state changes
- Expected-version checks prevent lost updates
- Worker serialises command execution against the pipeline
- Frontend is safe by construction — it cannot mutate state except through commands

### Negative

- Command lifecycle adds latency between operator action and state change
- Frontend must poll for command completion
- Worker must be running for commands to execute

## References

- ADR-0043 (Durable Command Model)
- ADR-0044 (Persistent Docker Volumes)

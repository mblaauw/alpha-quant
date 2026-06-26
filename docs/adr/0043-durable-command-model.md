# ADR-0043: Durable Command Model for Dashboard Mutations

## Status

Accepted

## Date

2026-06-26

## Context

Alpha-Quant's dashboard operational console allows operators to perform mutations: halting/resuming the system, running decision cycles, canceling orders, creating books, and appending journal notes.

These mutations must be:

- **Idempotent** — safe to retry without duplicate effects
- **Audited** — every mutation produces an audit trail
- **Version-safe** — concurrent modifications detect conflicts via optimistic concurrency
- **Asynchronous** — long-running work (decision runs, backtests) must not block HTTP requests
- **Durable** — survived process restarts and container rotations

## Options Considered

1. **Direct SQL mutations from HTTP handlers** — simplest but lacks idempotency, audit trail, and concurrency control
2. **Domain service calls from HTTP handlers** — better separation but long-running work blocks the request and risks timeouts
3. **Durable command table with worker** — commands are persisted before execution, processed asynchronously by a dedicated worker, and provide full lifecycle tracking

## Decision

All dashboard mutations become durable commands persisted in a dedicated `ops.command` table before execution.

The command lifecycle follows this flow:

```
requested -> validated -> queued -> running -> succeeded | failed | cancelled
```

The command envelope includes:

- `type` — command type identifier (e.g. `halt.create`, `decision_run.create`)
- `idempotency_key` — unique per actor+type for idempotent submission
- `actor_id` and `actor_display_name` — operator identity
- `book_id` — target portfolio book
- `expected_version` — optimistic concurrency version
- `reason` — operator-provided reason
- `payload_json` — typed command payload

A background worker (`alpha-quant worker`) claims queued commands using PostgreSQL `SKIP LOCKED`, dispatches them to typed handlers, and records the result. Long-running commands never execute inside HTTP request handlers.

## Consequences

**Positive:**

- Idempotency prevents duplicate commands from retries or double-clicks
- Every mutation leaves an audit trail in `audit.audit_event`
- Optimistic concurrency prevents silent overwrites
- Long-running work is processed by the worker, not HTTP handlers
- Command status polling enables the UI to show progress

**Negative:**

- Additional infrastructure: worker process, command table, polling
- Commands are eventually consistent — the UI must poll for completion
- Handler registration must be explicit for each command type (no automatic dispatch)

## Related

- ADR-0037 (PostgreSQL Operational System of Record)
- ADR-0038 (Append-Only Ledger with Rebuildable Projections)

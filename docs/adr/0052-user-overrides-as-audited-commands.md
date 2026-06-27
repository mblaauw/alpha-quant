# ADR-0052: User Overrides Are Audited Commands

## Status

Accepted

## Date

2026-06-27

## Context

Users can follow, modify, or reject advice recommendations. These actions mutate
the paper portfolio or record a permanent override decision. The system needs
to track every override with actor, reason, original recommendation, and timestamp.

## Decision

Every user override is a first-class durable command with full audit history.

- **follow**: Creates a paper order through the existing order submission flow
  (candidate.follow command).
- **modify**: Creates a modified paper order (candidate.modify command) with
  user-specified quantity or limit price.
- **reject**: Records an operator_override row and marks the candidate as
  operator-excluded. Does NOT mutate any position.
- **audit.operator_override** table stores: override_id, scorecard_id, command_id,
  actor_id, original_recommendation, original_confidence, override_action,
  modified_recommendation, reason, created_at.

## Consequences

Positive:
- Complete audit trail for every user override.
- Override data is queryable for performance analysis.
- Same command lifecycle as system actions (idempotent, durable, pollable).

Negative:
- Every user action requires a round-trip through the command worker.
- Additional storage for override rows.

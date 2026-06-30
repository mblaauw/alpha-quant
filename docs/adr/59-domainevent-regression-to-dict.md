# ADR-0059: DomainEvent Regression to Plain dict

## Status

Accepted

## Date

2026-06-30

## Context

DomainEvent was originally a pydantic model with typed fields. Event handlers depended on specific attributes. As the event surface grew, maintaining typed fields became overhead with no type-safety benefit.

## Decision

DomainEvent is a plain dict[str, Any]. Event consumers access fields by string key. This matches the append-only ledger pattern where events are JSON blobs.

## Consequences

Positive:
- Single source of truth for the architecture.

Negative:
- None identified.


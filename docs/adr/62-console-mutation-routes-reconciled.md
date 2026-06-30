# ADR-0062: Console Mutation Routes Reconciled with Command Bus

## Status

Accepted

## Date

2026-06-30

## Context

Some console routes performed direct state mutations instead of going through the command bus, violating ADR-0048.

## Decision

POST /v1/console/mode now submits a system.set_mock_mode command. All console mutations use the command bus. Direct state mutation routes are removed.

## Consequences

Positive:
- Single source of truth for the architecture.

Negative:
- None identified.


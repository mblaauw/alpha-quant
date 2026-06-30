# ADR-0066: FakeOperationalStore Enables Containerless Testing

## Status

Accepted

## Date

2026-06-30

## Context

All tests required PostgreSQL, making CI slow and local development complex. Developers needed Docker running for basic unit tests.

## Decision

FakeOperationalStore is an in-memory implementation of OperationalStorePort. Unit tests use it exclusively. Only integration tests require PostgreSQL. make test-fast runs 200+ tests in under 10s.

## Consequences

Positive:
- Single source of truth for the architecture.

Negative:
- None identified.


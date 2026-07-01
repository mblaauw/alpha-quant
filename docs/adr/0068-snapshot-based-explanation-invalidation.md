# ADR-68: Calculation-Snapshot-Based Explanation Invalidation

## Status

Accepted

## Date

2026-06-30

## Context

LLM-generated explanations are expensive and slow compared to deterministic calculations. If explanations are not bound to exact calculation snapshots, users may see stale explanations that no longer match the current deterministic state.

The codebase already has `facts_hash`, `config_hash`, and `RiskPolicy.config_hash()` for deterministic fingerprinting, but no unified snapshot concept that links scoring, risk, and explanation.

## Decision

Every explanation result is keyed to a `CalculationSnapshot` composite identifier:

- `snapshot_id`: SHA-256 hash of `facts_hash + config_hash + scorecard_id` (for scorecard explanations) or `risk:{as_of}` (for risk explanations)
- `input_fingerprint`: SHA-256 hash of the specific input context dict used for that generation

When a new daily cycle or risk calculation runs:

1. A new `CalculationSnapshot` is created
2. Existing explanations for the same scope are marked `stale=True` via `mark_explanations_stale()`
3. New explanation requests are generated for the new snapshot
4. In-flight generation jobs carry the `snapshot_id` they were requested for — if it no longer matches the latest, the result is discarded

The `mark_explanations_stale()` port method and its implementations in both FakeOperationalStore and PostgresOperationalStore enforce this lifecycle.

## Consequences

Positive: Users never see stale explanations as current; late responses are safely discarded; cache keys are deterministic.

Negative: Slightly more complex generation flow; requires store support for the stale flag.

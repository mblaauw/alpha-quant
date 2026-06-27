# ADR-0049: Alpha-Lake Facts Bundle as Primary Scorecard Data Source

## Status

Accepted

## Date

2026-06-27

## Context

Alpha-Quant needs structured, pre-computed neutral facts for each symbol to produce
deterministic scorecards. Two sources are available from Alpha-Lake:

1. The `GET /v1/decision-panel` endpoint (legacy) — returns bars, raw indicators,
   fundamentals, insider facts in a nested panel structure.
2. The `GET /v1/symbol/{symbol}/facts-bundle` endpoint (new) — returns structured
   readouts, fundamentals, insider transactions, earnings events, and attention
   mentions in a flat, versioned bundle.

The scorecard engine (P3) requires structured readouts with definitions and
observation series, not raw indicator arrays.

## Decision

Use the facts-bundle endpoint as the primary data source for the new scorecard
and advice workflow. The legacy decision-panel endpoint is kept only for backward
compatibility with the existing DuckDB-backed pipeline_v2.

Key design decisions:

- **Single-symbol calls** for production (batch endpoint used only for research
  and exploration, marked explicitly as non-research when used).
- **Explicit `as_of` required** — no `latest=true` from the domain path. Every
  scorecard call carries an explicit point-in-time timestamp.
- **Readout definitions are stable** — Alpha-Lake owns the readout_id
  namespace. AQ stores facts_hash but does not cache individual readout
  definitions.
- **Batch calls** default missing `as_of` to current time. AQ MUST always
  provide `as_of` in batch calls to ensure reproducibility.

## Consequences

Positive:
- Cleaner data model for scorecards (structured readouts vs raw indicator arrays).
- Deterministic reproducibility: same `(symbol, as_of, snapshot_id)` always
  returns the same bundle.
- Facts bundle includes all sections (readouts, fundamentals, insider, earnings,
  mentions) in a single response.

Negative:
- Single-symbol calls for N symbols produce N HTTP requests instead of 1 batch.
- The legacy decision-panel path must be maintained until the DuckDB pipeline
  is fully migrated.

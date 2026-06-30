# ADR-0060: Risk Engine Uses Synthetic Returns as v1 Methodology

## Status

Accepted

## Date

2026-06-30

## Context

The risk engine requires daily return series for covariance, VaR, ES, and beta computation. Real historical returns are not available from Alpha-Lake's PIT API.

## Decision

Synthetic returns are generated via deterministic LCG per position. This is v1 methodology — acceptable for relative comparisons within a single run. Real returns from Alpha-Lake will replace synthetic in v2.

## Consequences

Positive:
- Single source of truth for the architecture.

Negative:
- None identified.


# ADR-0065: LLM Integration and Guardrails for Deterministic Advice

## Status

Accepted

## Date

2026-06-30

## Context

LLM explanations were desired for advice artifacts, but LLMs are non-deterministic and can hallucinate prices or positions.

## Decision

LLM explains deterministic scorecard results only. CannedLLM provides fallback JSON. validation_status is verified/unverified/failed. Retry limit is 3 attempts.

## Consequences

Positive:
- Single source of truth for the architecture.

Negative:
- None identified.


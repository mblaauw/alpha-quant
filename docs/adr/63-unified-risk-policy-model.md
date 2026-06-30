# ADR-0063: Unified Risk Policy Model Replaces Three Disconnected Systems

## Status

Accepted

## Date

2026-06-30

## Context

Three disconnected policy systems existed: RiskConfig (domain/risk.py, never read), PolicyLimits (risk/limits.py, never configured), and sizing guardrails (console_routes.py, inconsistent thresholds).

## Decision

RiskPolicy in domain/risk.py is the single model for all thresholds. It replaces RiskConfig and PolicyLimits. Pre-trade and post-trade checks share the same policy values.

## Consequences

Positive:
- Single source of truth for the architecture.

Negative:
- None identified.


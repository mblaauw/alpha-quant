# ADR-0064: Scoring Policy Versioning via RiskPolicy.component_weights_json

## Status

Accepted

## Date

2026-06-30

## Context

Scorecard component weights were hardcoded in _COMPONENT_WEIGHTS. Changing weights required a code deployment. No versioning or audit trail existed for weight changes.

## Decision

Component weights are configurable via RiskPolicy.component_weights_json. The config_hash captures weight values for deterministic replay. Weights default to _COMPONENT_WEIGHTS when not overridden.

## Consequences

Positive:
- Single source of truth for the architecture.

Negative:
- None identified.


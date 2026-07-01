# ADR-0057: Scorecard Engine Replaces Policy Modules as Decision Core

## Status

Accepted

## Date

2026-06-30

## Context

Originally Alpha-Quant used discrete strategy policy modules (M1-M8 as separate Python classes) to evaluate securities. These were replaced by a unified scorecard engine that produces 13 scored components from FactsBundle data.

## Decision

The scorecard engine is the single decision core. All 13 component scorers are in scorecards.py. M1-M8 mapping is a UI concern in domain/categories.py.

## Consequences

Positive:
- Single source of truth for the architecture.

Negative:
- None identified.


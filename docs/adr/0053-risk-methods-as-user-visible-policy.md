# ADR-0053: Risk Methods Are User-Visible, Deterministic Policies

## Status

Accepted

## Date

2026-06-27

## Context

Position risk (stops, trailing, time limits) was previously configured in
config files and applied automatically by the pipeline. The advice workflow
requires risk methods to be user-selectable, explainable, and visible in the
Desk UI.

## Decision

Risk methods are user-visible, deterministic policy objects with:
- A unique method type (e.g., `fixed_percent`, `atr_trailing`, `time_stop`).
- Type-specific parameters (e.g., `pct`, `multiplier`, `max_holding_days`).
- A deterministic computation function that returns a RiskCalculation with
  stop_price, trail_price, time_stop_date, and a human-readable reason.
- Registration in METHOD_REGISTRY for runtime lookup.

Seven initial methods: fixed_percent, atr_initial, atr_trailing, time_stop,
profit_protection, drawdown_ladder, conservative_blended.

## Consequences

Positive:
- Methods are explainable: each RiskCalculation includes a human-readable reason.
- User can switch methods per book or per position.
- Conservative blended method provides a safe default.
- No LLM involvement in risk — pure deterministic math.

Negative:
- More UI surface area for method selection.
- Per-position method overrides add complexity to the data model.

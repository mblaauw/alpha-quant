# ADR-0047: Operational Context Is Not Global PIT Context

## Status

Accepted

## Date

2026-06-27

## Context

Alpha-Lake Lake Watch uses a global `as_of` (point-in-time) selector and snapshot context because it is a fact-exploration system. Every screen reinterpret data through the selected timestamp.

Alpha-Quant is an operational system. Its current portfolio state is the result of actual decisions, fills, and risk actions — not a time-travel query. Applying a global timestamp to operational views would present an incorrect portfolio state and could lead to unsafe operator decisions.

Historical run context is different: a selected historical run owns its own immutable context (decision_as_of, snapshot_id, strategy version, policy hash). That context must not leak into the global operational view.

## Decision Drivers

- **Safety** — current portfolio state must always reflect actual executed state, not a reinterpretation
- **Determinism** — historical run context is immutable; changing it would break reproducibility
- **Operator clarity** — mixing current and historical context creates confusion about what is actionable

## Decision Outcome

Alpha-Quant does not apply a global `as_of` selector to current operational portfolio state.

Two context modes exist:

1. **Operational context (global)** — active book, mode, operational status, halt state, last run, Alpha-Lake health
2. **Historical run context (immutable, scoped)** — decision run ID, book, strategy version, policy hash, decision_as_of, execution_as_of, snapshot_id, artifact reference

### Rules

- The global top bar shows operational context only
- When viewing a historical run, a persistent banner shows the run's immutable context
- Operational mutation actions are disabled when viewing historical context
- A historical run's `as_of` value never alters current portfolio views
- The Desk view always reflects the current operational state, not a historical snapshot

## Consequences

### Positive

- Operators always see the true current portfolio state
- Historical runs are inspectable without risk of confusion
- No complex global time-travel state management

### Negative

- Operators cannot "time travel" the current portfolio — must inspect historical runs separately
- Slightly more UI work to show both current and historical context

## References

- ADR-0033 (PIT reads via Clock-driven as_of)
- Alpha-Lake Lake Watch global as_of pattern (not copied)

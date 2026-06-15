# ADR-0024: Use Self-Consistency Invariants for Portfolio Integrity

## Status

Accepted

## Date

2026-06-12

## Context

In a brokerless paper-trading system, there is no external counterparty to reconcile against. Portfolio integrity relies entirely on internal consistency checks. A violation is a software bug and must trigger a full halt (I12).

The system invariants (DESIGN.md §16) include:
- I1: `abs(cash + total_market_value - equity) < 0.01`
- I5: Per-position risk-at-stop ≤ 2% of equity at order time
- I6: Gross exposure ≤ cap after every fill batch
- I12: The paper book passes self-consistency after every fill batch; violation ⇒ full halt

During Phase 2, invariant checks were implemented as standalone pure functions rather than inline assertions scattered across modules.

## Decision Drivers

- **Pure function** — Invariant checks must be deterministic, side-effect-free, and testable
- **Composable checks** — Each invariant is a separate function; they compose into a single check
- **Standardized output** — All violations return `InvariantViolation(check, detail)` for uniform handling
- **Caller decides action** — The domain function returns violations; the caller (pipeline/PaperPortfolio) decides whether to halt, log, or continue

## Considered Options

- **Option A: Dedicated invariants module (current choice)** — `domain/invariants.py` with `check_invariants()` and structured `InvariantViolation` output
- **Option B: Inline assertions** — `assert` statements scattered through portfolio mutation code
- **Option C: Property-based test suite** — Invariants checked only in tests via hypothesis, not at runtime

## Decision Outcome

Chosen option: **Option A — Dedicated invariants module**.

Rationale:
1. Pure functions are testable in isolation — no store, no portfolio state needed
2. `InvariantViolation` is a simple dataclass, not a runtime exception — the caller controls whether to raise, log, or continue
3. The same `check_invariants()` function is used by both `PaperPortfolio.self_consistency_check()` and `app/pipeline.py` run-final check
4. Inline assertions (Option B) cannot be composed or silenced — a single failed assertion crashes the process without capturing context

### Positive Consequences

- Self-consistency checks are O(n) in the number of positions
- Violations include human-readable detail (actual vs expected values, symbol names)
- The pipeline converts violations to `ConsistencyViolation` events for the event log
- Easy to add new invariants: write a `_check_*()` function and add it to `check_invariants()` aggregation

### Negative Consequences

- Invariants only check what is explicitly coded — gaps in invariant coverage mean silent corruption
- I1 (cash + mark == equity) requires the caller to provide the equity value — if the caller provides wrong equity, the check passes but state is corrupt
- No property-based testing for invariants (hypothesis was removed as an unused dependency — see ADR-0027)

## References

- DESIGN.md §9.3: Self-consistency (replaces broker reconciliation)
- DESIGN.md §16: System invariants I1–I13
- `alpha_quant/domain/invariants.py`
- `alpha_quant/app/paper.py` — `self_consistency_check()`
- `alpha_quant/app/pipeline.py` — run-final self-consistency
- Refinement backlog P2.1: Property tests for invariants

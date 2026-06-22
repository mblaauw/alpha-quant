# ADR-0028: Use Clock Virtualization for Deterministic Replay

## Status

Accepted

## Date

2026-06-15

## Context

Alpha-Quant's golden replay CI and fixture-based backtesting require deterministic time. Every pipeline run must produce identical decisions when given identical input data, regardless of when or where the run executes. A system clock (`datetime.now(UTC)`) breaks determinism because it produces different timestamps on every run.

Three execution modes consume clock values:
- **Fixture/Replay mode** — steps through a fixed date range, one day per virtual tick
- **Live mode** — queries the real system clock for the current trading date
- **Backtest mode** — iterates over historical dates

All three must share the same domain logic. The clock abstraction must be transparent to domain code — no domain function should read the OS clock.

## Decision Drivers

- **Determinism (I7/I9)** — Identical inputs must produce identical outputs. Real clocks produce non-identical timestamps
- **Domain purity** — Domain functions must never read the OS clock directly. Clock is an injected dependency
- **Three modes** — fixture/replay, live, and backtest each need a different clock implementation
- **Swap at boundary** — The clock is injected at the app layer, not hardcoded in adapters or domain

## Considered Options

- **Option A: Clock port with two implementations (current choice)** — `ports/clock.py` defines `Clock(ABC)` with `today() -> date`. `SystemClock` wraps `datetime.now(UTC)`. `VirtualClock` exposes `advance(days)` for deterministic stepping
- **Option B: Pass date as parameter everywhere** — Every function receives `today: date` explicitly. No clock abstraction needed
- **Option C: Environment variable override** — `OVERRIDE_DATE` env var for testing, real clock otherwise
- **Option D: Monkey-patch in tests** — Replace `datetime.now` with a mock during test setup

## Decision Outcome

Chosen option: **Option A — Clock port with two implementations**.

Rationale:
1. The port abstraction isolates domain code from any clock implementation — no domain function reads the OS clock
2. `VirtualClock` is the foundation of golden replay determinism — the replay loop calls `advance(1)` after each day
3. `SystemClock` is a trivial wrapper (5 lines) — minimal maintenance cost
4. Explicit date parameter (Option B) would require threading `today` through every function signature — noisy and error-prone
5. Env var override (Option C) is fragile — can affect unrelated processes
6. Monkey-patching (Option D) does not compose — parallel tests with different dates are impossible

### Positive Consequences

- Golden replay is deterministic by construction (I7, I9)
- Backtest and replay share the same loop logic with different clock implementations
- No domain code imports `datetime.now` — verified by CI invariant check
- `VirtualClock` supports `advance()`, `resume()`, and date query — sufficient for all replay scenarios

### Negative Consequences

- An extra indirection layer for what could be `datetime.now(UTC).date()` in live mode
- The `VirtualClock` must be carefully reset between CI runs to avoid state leakage

## Amendment (2026-06-21)

Clock drives lake `as_of` for all PIT reads.

## References

- ADR-0017 (Golden Replay CI)
- ADR-0021 (DuckDB for transactional state)
- DESIGN.md §1 (Architecture overview — port isolation)
- `ports/clock.py`
- `adapters/real/clock.py` (SystemClock)
- `adapters/fake/virtual_clock.py`

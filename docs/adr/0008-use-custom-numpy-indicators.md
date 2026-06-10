# ADR-0008: Use Custom numpy Recurrences for Technical Indicators

## Status

Accepted

## Date

2026-06-10

## Context

The technical scoring mechanism (M3) requires EMA(20/50/200), RSI(14), ATR(14), MACD, and 12-1 momentum. These must be computed daily for 50+ symbols. The system design (§3.5) mandates O(1) incremental updates — compute the new value from the previous state and the new bar, without recomputing windows.

DESIGN.md §3.8 specifies "numpy recurrences (own ~100 lines) — incremental O(1); window libs unnecessary."

## Decision Drivers

- O(1) per-symbol-per-day update: no window recomputation, no data dependency beyond the previous state
- 50-day raw tail with 200-day EMAs: window-based libraries would require keeping 200+ days of raw data for each symbol
- Cold start: one-time 250-day backfill seeds the state, then raw bars are pruned
- CI integrity check: recompute from full history, compare to incremental state to 1e-6
- No license or attribution requirements

## Considered Options

- **Option A: Custom numpy recurrence formulas (~100 lines)** — EMA Wilder/EMA recurrences implemented directly in numpy
- **Option B: pandas-ta** — 130+ indicators, but all are window-based (requires keeping full history); O(n) per call
- **Option C: TA-Lib** — Industry standard, fast C implementations, but O(n) window recomputation; complex installation (needs C library)
- **Option D: Numba/Cython** — Would optimize window-based computation, but unnecessary when recurrence is O(1)

## Decision Outcome

Chosen option: **Option A — Custom numpy recurrence formulas**.

Rationale:
1. Only 5 indicators are needed — building custom numpy recurrences is ~100 lines of code
2. O(1) per update enables the 50-day raw tail pattern: EMA200 is computed from a single stored value, not 200 days of history
3. Zero external dependency — no pandas-ta or TA-Lib installation issues
4. The team already uses numpy — no new skills required
5. CI integrity check detects any drift from the brute-force computation

### Positive Consequences

- The 50-day tail pattern works (EMA200 = 0.5 kB of stored state, not 200 days of OHLCV)
- Performance: 10,000 symbols × 1 update in < 10ms
- Total code footprint: ~100 lines of pure numpy, no abstractions
- Deterministic and auditable — the recurrence formula is visible in the source code

### Negative Consequences

- Must implement and test each indicator manually (rather than calling a library function)
- Adding a new indicator (e.g., Bollinger Bands, Ichimoku) requires implementing its recurrence formula
- Team must understand the recurrence math (Wilder smoothing, EMA alpha)
- No TA-Lib's performance for non-recurrence indicators (but none are needed for v1)

## References

- DESIGN.md §3.5 (Derived state), §3.8 (Library decisions)
- RAD §6.1 (Data Layer Components — Derive Engine)
- C4 Component diagram (Data Layer): `docs/architecture/views/data-layer-components.png`
- ADR-0015 (Incremental O(1) indicator engine architecture)

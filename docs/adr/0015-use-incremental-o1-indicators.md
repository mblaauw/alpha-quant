# ADR-0015: Use Incremental O(1) Indicator Engine

## Status

Accepted

## Date

2026-06-10

## Context

The indicator engine (derive.py) must compute EMA(20/50/200), RSI(14), ATR(14), MACD, and 12-1 momentum for each symbol every day. The 50-day raw tail (DESIGN §3.5) means long-window indicators (EMA200) cannot be recomputed from available raw data. The indicator state must persist between runs and update incrementally.

This ADR documents the *how* at the architecture level, while ADR-0008 documents the *what* (choice of numpy recurrences).

## Decision Drivers

- O(1) per indicator per symbol per day: no window scans, no database reads of historical bars
- Stateful: indicator state persists in SQLite between pipeline runs
- Cold start: bootstrap does a one-time 250-day backfill to seed the state
- Integrity verification: CI recomputes from full fixture history and compares to incremental state (1e-6 tolerance)
- The 50-day tail pattern only works if indicators are maintained incrementally

## Considered Options

- **Option A: Incremental O(1) state machine** — Store `{ema20, ema50, ema200, rsi_avg_gain, rsi_avg_loss, atr, last_close}` for each symbol; update via recurrence formulas
- **Option B: Keep full raw history and recompute windows** — Defeats the purpose of the 50-day tail (would need to keep 200+ days of raw bars)
- **Option C: Window-based with database window functions** — Compute indicators via SQL window functions (DuckDB or SQLite); requires keeping all raw data; slower for single-symbol updates

## Decision Outcome

Chosen option: **Option A — Incremental O(1) state machine**.

Rationale:
1. The 50-day tail is only achievable with incremental state — keeping 200+ days of raw data for 50 symbols just to compute EMA200 is wasteful
2. Performance: 50 symbols × 5 indicators = 250 O(1) updates per day, executed in < 1ms
3. The indicator state is a single SQLite row (~200 bytes per symbol) — 50 symbols = 10 KB of state
4. Cold start is a one-time bootstrap operation (DESIGN §3.7) that runs on project initialization
5. Integrity check in CI catches any drift from the brute-force computation

### Positive Consequences

- Raw bars can be pruned to the 50-day tail immediately after indicator update
- Indicator state is human-readable in SQLite (inspectable via `sqlite3`)
- Adding a new indicator is a single recurrence formula + one more column in the indicator_state table
- The derive engine is pure numpy — trivially testable

### Negative Consequences

- Cold start requires a one-time backfill (250 days of bars per symbol) — this is handled by the bootstrap command and is a one-time cost
- RSI and ATR use modified Wilder smoothing (different from standard RMA/ATR implementations) — must be documented clearly in the concept cards
- State corruption (e.g., NaN in a stored value) would silently affect all subsequent updates — the validation gate (validate.py) must catch this

## References

- DESIGN.md §3.5 (Derived state / incremental engine), §3.7 (Bootstrap)
- RAD §6.1 (Data Layer Components — Derive Engine)
- C4 Component diagram (Data Layer): `docs/architecture/views/data-layer-components.png`
- ADR-0008 (Custom numpy indicators)

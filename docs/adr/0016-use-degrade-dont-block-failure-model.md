# ADR-0016: Use Degrade-Don't-Block Data Failure Model

## Status

Accepted

## Date

2026-06-10

## Context

Alpha-Quant depends on five external data sources with varying reliability. A single source failure should not halt the entire system. Each mechanism has a defined fallback behavior when its data source is unavailable.

DESIGN.md §3.2 specifies: "a source failing degrades, never blocks — pipeline runs with SOURCE_DEGRADED(source) event; mechanisms depending on it fall back. Only price staleness sets DATA_HALT."

## Decision Drivers

- No single point of failure: a Reddit API downtime should not prevent the daily run
- Defined fallbacks: every mechanism must specify what it does when its data is missing
- Only price data is critical: stale prices mean the portfolio cannot be accurately valued, which is a halt condition
- User visibility: degradation must be surfaced in the daily journal and dashboard (not silently absorbed)

## Considered Options

- **Option A: Degrade-don't-block (per DESIGN §3.2)** — Each source has defined fallback; only price staleness halts
- **Option B: Fail-fast** — Any source failure prevents the pipeline from running — simple but fragile
- **Option C: Stale-data-with-warning** — Continue with stale data indefinitely, log a warning; too risky for price data

## Decision Outcome

Chosen option: **Option A — Degrade-don't-block**.

Rationale:
1. Three of five sources (OpenInsider, Reddit, SEC) are non-critical — their data enhances decisions but is not essential. Blocking the pipeline for these would be a poor tradeoff
2. EODHD fundamentals and earnings calendar have defined fallbacks (pass-through with degraded event, widened blackout window)
3. Only EODHD daily bars and Alpaca quotes are price data — staleness here prevents accurate portfolio valuation and risk measurement, so halt is correct
4. Degradation events are surfaced in the daily journal (DESIGN §12) — the user sees "Reddit source degraded today, M6 crowding veto disabled"
5. This is the standard approach in production trading systems: survive through data issues, don't crash

### Positive Consequences

- The pipeline runs daily regardless of non-critical source availability
- Fallback behaviors are explicit and testable (source degradation chaos tests in P5.6)
- The user is always informed of data quality via the daily journal
- Source degradation recovery is automatic — next pipeline run after source comes back

### Negative Consequences

- More complex than fail-fast (each mechanism needs a fallback path)
- Degradation must be monitored (alerting in P5.3 catches prolonged outages)
- If EODHD (the primary source) degrades, the system still runs but with degraded data — the user might not notice without checking the journal

## References

- DESIGN.md §3.2 (Connectors — Failure policy), §16 (Invariants)
- RAD §4 (System Context), §10 (Cross-Cutting Concerns — Security)
- C4 System Context diagram: `docs/architecture/views/system-context.png`
- Chaos tests: STORY-5.6, BACKLOG.md

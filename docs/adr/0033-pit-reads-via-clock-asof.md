# ADR-0033: PIT Reads via Clock-Driven `as_of`

**Status:** Accepted

**Date:** 2026-06-21

## Context

Alpha-Quant's pipeline processes one day at a time, driven by the Clock port (ADR-0028). Every component that reads source data (bars, fundamentals, insider transactions) must see a consistent snapshot: the data that was available as of the current processing date, not data from the future.

Before Alpha-Lake (ADR-0032), this consistency was implicit — the canonical Parquet store was append-only and date-partitioned, so reading `bars/dt <= today` naturally produced the right view. However, this approach had problems:

1. **No enforcement.** Nothing prevented a read from accidentally including future data (e.g., a query missing the `dt` filter).
2. **Hard to replay.** During replay, the same data must be produced regardless of wall-clock time. Without an explicit `as_of`, queries could return different results depending on how much data had been ingested.
3. **Fixture mismatch.** Fixture bundles were pre-loaded snapshots; their "as of" was implicit in the bundle creation date, not explicit in the query.

Alpha-Lake's datasets are append-only but not date-partitioned in the same way. A deterministic `as_of` parameter is needed to ensure every read returns a point-in-time consistent view.

## Decision

**All lake reads use `clock.now()` as `as_of`.** The LakeGateway's read methods accept an optional `as_of: date` parameter; when omitted, it defaults to `clock.now()` (the current virtual or system date).

Specific rules:

- `LakeGateway.bars(symbol, as_of=clock.now())` returns bars with `dt <= as_of`.
- `LakeGateway.fundamentals(symbol, as_of=clock.now())` returns the most recent fundamentals snapshot on or before `as_of`.
- `LakeGateway.insider_transactions(symbol, as_of=clock.now())` returns transactions filed on or before `as_of`.
- During replay (VirtualClock), `clock.now()` advances one day per tick, so every day's reads are automatically scoped to that day.
- During live mode (SystemClock), `clock.now()` returns today's actual date, so reads see all data ingested so far today.

### Walk-Forward Determinism

The Clock-driven `as_of` guarantees walk-forward determinism (I7):

```text
Input: fixture data loaded at virtual date 2024-01-01
Day 1: clock.now() = 2024-01-01 → as_of = 2024-01-01
Day 2: clock.advance(1) → clock.now() = 2024-01-02 → as_of = 2024-01-02
...
```

The same fixture + same clock sequence always produces the same `as_of` sequence, hence the same query results.

### Validation

A CI invariant (I10) checks that every LakeGateway read in the domain layer passes an `as_of` derived from the clock — no bare `SELECT * FROM bars` without date scoping.

## Consequences

### Positive

- Deterministic walk-forward by construction: every read is scoped to the current virtual date
- No accidental future-data leaks: omitting `as_of` is a type-checker error (required parameter in the port signature)
- Fixture bundles are simple: they are pre-loaded datasets; the `as_of` parameter controls the visible window
- Live mode works identically: the same code path with SystemClock produces the correct live view

### Negative

- Read methods must accept `as_of` everywhere — slightly more verbose than implicit date scoping
- The lake must support efficient filtered scans by `dt <= as_of` for large datasets
- If `clock.now()` is wrong (e.g., clock not advanced during replay), reads return stale/empty results — mitigated by CI invariant I10

## References

- ADR-0028 (Clock virtualization for determinism)
- ADR-0032 (Alpha-Lake as the sole data plane)
- ADR-0034 (LakeGateway port and adapters)

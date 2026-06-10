# ADR-0017: Use Golden Replay as the Primary CI Strategy

## Status

Accepted

## Date

2026-06-10

## Context

Alpha-Quant is a deterministic system (I7: identical inputs + config + git sha ⇒ identical decisions and fills). This property should be the foundation of the QA strategy. The highest-leverage testing investment is the golden replay: running the entire pipeline against a fixed fixture dataset and comparing outputs to a committed golden file.

DESIGN.md §4 states: "CI runs a golden replay (6 fixture-months; decision log + paper equity curve must hash-match the committed golden output)."

## Decision Drivers

- Maximum confidence per CI run: the golden replay exercises the entire pipeline (data → indicators → decisions → fills → P&L)
- Determinism means the golden test is not flaky — identical inputs always produce identical outputs
- Catch regressions early: a golden hash mismatch alerts the team that a code change affected system behavior
- Low maintenance: updating the golden file is a deliberate action (`make bless-golden`) that requires code review

## Considered Options

- **Option A: Golden replay with hash comparison** — Run full DAG on fixtures, compare SHA256 of decision log + equity curve to committed golden file
- **Option B: Unit tests only** — Test individual functions in isolation; no integration test across the full pipeline
- **Option C: Snapshot testing (pytest-snapshot)** — Compare individual outputs to saved snapshots; more granular but more maintenance
- **Option D: No CI integration testing** — Rely on developer manual testing — unacceptable for a financial system

## Decision Outcome

Chosen option: **Option A — Golden replay with hash comparison**.

Rationale:
1. The golden replay exercises the entire DAG — from data ingestion through fill booking — in a single CI job
2. Determinism (I7) means the golden test NEVER fails due to environmental factors — every failure is a real regression
3. 6 fixture-months of data provides high confidence that the change is correct
4. `make bless-golden` makes updating the golden file an explicit, reviewable action (it changes the golden hash in the PR)
5. Unit tests remain important for edge cases, but the golden replay catches integration-level regressions that unit tests miss

### Positive Consequences

- Any regression in data parsing, indicator computation, decision logic, fill execution, or P&L calculation is caught in CI
- The golden file serves as living documentation of expected system behavior
- New contributors can verify their changes pass the golden replay before submitting PRs
- The golden replay completes in < 3 minutes for 6 fixture-months (fits comfortably in CI time budget)

### Negative Consequences

- Maintaining the golden file: when the golden file intentionally changes, the PR must include the re-blessed golden output and a clear explanation of why
- The golden replay is a coarse check (hash of entire output) — a regression in one symbol's fill is detected, but debugging requires examining the diff
- Golden replay does not replace unit tests for edge cases and property-based testing

## References

- DESIGN.md §4 (Clock virtualization and replay), §16 (Invariant I7)
- RAD §10 (Cross-Cutting Concerns — Testing Strategy)
- STORY-0.8 (Golden replay CI), BACKLOG.md

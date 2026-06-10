# ADR-0001: Use Python 3.12 LTS as the Runtime

## Status

Accepted

## Date

2026-06-10

## Context

Alpha-Quant is a deterministic, daily-cadence quant trading system written entirely in Python. The choice of Python version affects library compatibility, performance characteristics, and long-term maintainability. The project has no dependency on Python 3.13+ exclusive features (free-threaded mode, t-strings).

Key considerations:
- Library wheel availability for all planned dependencies (numpy, pydantic, DuckDB, etc.)
- GIL-free / free-threaded Python (3.13 experimental) offers no benefit for a single-threaded daily pipeline
- The 50-day tail with O(1) numpy recurrences has trivial compute requirements
- Team familiarity and deployment environment stability

## Decision Drivers

- Maximum library compatibility with zero build-from-source requirements
- Minimum 3 years of security support from upstream
- No performance bottleneck that free-threaded Python would solve
- Ecosystem maturity — all planned dependencies must have published wheels

## Considered Options

- **Option A: Python 3.12 LTS** — Conservative, widest wheel support, supported until Oct 2028
- **Option B: Python 3.13** — Free-threaded mode available, but still experimental; some libraries (numpy 2.0+, pydantic) require 3.13-specific wheels
- **Option C: Python 3.14** — Latest, t-string support, `compression.zstd` in stdlib; many libraries still testing wheels

## Decision Outcome

Chosen option: **Option A — Python 3.12 LTS**.

Rationale:
1. All planned libraries have published 3.12 wheels (zero compilation needed)
2. 3.12's performance is sufficient — the daily pipeline processes ~50 symbols with O(1) indicator updates; total CPU time per run is < 1 minute
3. 3.13's free-threaded (no-GIL) mode provides no benefit for a single-threaded pipeline
4. 3.14's new features (t-strings, zstd in stdlib) are not transformative enough to justify the compatibility risk
5. Upgrading later is trivial (change `python_requires` in `pyproject.toml`) if a concrete need arises

### Positive Consequences

- Widest possible library compatibility (numpy 2.x, DuckDB, pydantic all shipping 3.12 wheels)
- No CI surprises from alpha-stage CPython features
- Clear upgrade path: 3.12 → 3.13 → 3.14 when the ecosystem matures

### Negative Consequences

- Cannot use Python 3.13+ exclusive features (free-threaded, `@no_gil` decorator)
- `zstandard` third-party package required (3.14 will have it in stdlib, not a blocker)

## References

- DESIGN.md §3.8 (Library decisions)
- Python 3.12 release schedule: https://devguide.python.org/versions/
- RAD §3 (Technology Stack Summary)

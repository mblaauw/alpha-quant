# ADR-0001: Use Python 3.14 as the Runtime

## Status

Accepted (updated 2026-06-10 — originally 3.12, bumped to 3.14 for real-world availability)

## Date

2026-06-10

## Context

Alpha-Quant is a deterministic, daily-cadence quant trading system written entirely in Python. The choice of Python version affects library compatibility, performance characteristics, and long-term maintainability. Originally targeting 3.12 LTS for conservative compatibility, the actual development environment runs Python 3.14 and all core dependencies provide published 3.14 wheels.

Key considerations:
- Library wheel availability for all planned dependencies (numpy, pydantic, DuckDB, etc. all ship 3.14 wheels)
- GIL-free / free-threaded Python (3.13 experimental) offers no benefit for a single-threaded daily pipeline
- The 50-day tail with O(1) numpy recurrences has trivial compute requirements
- Python 3.14 brings `compression.zstd` to stdlib, eliminating the `zstandard` third-party dependency

## Decision Drivers

- Maximum library compatibility with zero build-from-source requirements
- Minimum 3 years of security support from upstream
- No performance bottleneck that free-threaded Python would solve
- Ecosystem maturity — all planned dependencies must have published wheels

## Considered Options

- **Option A: Python 3.12 LTS** — Conservative, widest wheel support, supported until Oct 2028
- **Option B: Python 3.13** — Free-threaded mode available, but still experimental
- **Option C: Python 3.14** — Latest stable, t-string support, `compression.zstd` in stdlib; all core libraries shipping 3.14 wheels

## Decision Outcome

Chosen option: **Option C — Python 3.14**.

Rationale:
1. All planned libraries have published 3.14 wheels (zero compilation needed at install time)
2. 3.14's performance is sufficient — the daily pipeline processes ~50 symbols with O(1) indicator updates; total CPU time per run is < 1 minute
3. 3.13's free-threaded (no-GIL) mode provides no benefit for a single-threaded pipeline
4. `compression.zstd` in stdlib simplifies the dependency tree
5. The actual development environment runs 3.14 — aligning `pyproject.toml` with reality avoids CI confusion
6. Downgrading to 3.12 is trivial if a library compatibility issue surfaces (change `python_requires`)

### Positive Consequences

- Access to t-strings and other 3.14 quality-of-life features
- `compression.zstd` in stdlib — one less third-party dependency
- CI matches the development environment exactly

### Negative Consequences

- Slightly narrower library compatibility surface than 3.12 (no known issues as of June 2026)
- Cannot use free-threaded Python if a future bottleneck emerges (unlikely for this workload)

## References

- DESIGN.md §3.8 (Library decisions)
- Python 3.14 release schedule: https://devguide.python.org/versions/
- RAD §3 (Technology Stack Summary)

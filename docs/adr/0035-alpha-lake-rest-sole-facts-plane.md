# ADR-0035: Alpha-Lake REST Is the Sole Alpha-Quant Runtime Facts Plane

**Status:** Accepted

**Date:** 2026-06-25

## Context

Alpha-Quant evolved through several data-plane architectures:

1. **P0–P1 (ADR-0006, ADR-0008, ADR-0012):** Direct provider connectors (EODHD, Tiingo, SEC) writing to a local DuckDB/Parquet canonical store with local indicator computation in numpy.
2. **P2–P3 / Alpha-Lake extraction (ADR-0032, ADR-0034):** Unified `LakeGateway` port with three adapter modes (fixture, in-process, REST). The in-process adapter imported `alpha_lake` Python modules directly, granting Alpha-Quant unfettered access to the lake's DuckDB connection and internal tables.
3. **P4 / REST-only reset (this ADR):** Eliminate all non-REST data access paths. Alpha-Quant may only consume market facts through Alpha-Lake's versioned authenticated HTTP API.

Each earlier architecture carried a different form of coupling: Python imports, DuckDB connections, Parquet file paths, provider API keys, and source-scraping scripts. This ADR closes all of them.

## Decision

**Alpha-Quant consumes all market facts exclusively through Alpha-Lake's authenticated versioned REST API.**

Direct Python imports, direct storage access, local providers, local canonical stores, local neutral-metric derivation, and runtime fallback modes are prohibited.

Fixture clients are allowed only in tests and offline replay.

### Enforcement rules

```
No Alpha-Lake Python modules imported at runtime.
No DuckDB/Parquet reads for market facts.
No source-provider clients (EODHD, Tiingo, SEC, OpenInsider, Reddit, Alpaca Data).
No in-process Alpha-Lake gateway.
No fixture mode selectable in production config.
No fallback to local canonical data.
No live broker execution.
```

### Failure semantics

When Alpha-Lake is unavailable, stale, incompatible, or cannot satisfy the requested `as_of`, Alpha-Quant must:

- Fail closed on the `run` command.
- Enter existing degraded/halt mode where applicable.
- Never silently fall back to local data.

### Replay and testing

Offline replay uses recorded Alpha-Lake HTTP response fixtures. The fixture client (`AlphaLakeHttpFixtureClient`) reads pre-recorded contract responses. No live HTTP calls, no current-time dependence, no Alpha-Lake Python imports.

## Consequences

### Positive

- Strict dependency boundary — Alpha-Quant cannot accidentally access lake internals.
- Single wire protocol — debugging requires only HTTP inspection.
- Fixture-based replay is portable and deterministic.
- No provider API keys, rate limits, or scraping code in Alpha-Quant.
- Security boundary — the API key gates all fact access.

### Negative

- Alpha-Quant is fully dependent on Alpha-Lake server availability for live runs.
- REST latency adds overhead compared to in-process DuckDB access.
- The decision-panel batch endpoint must be performant enough for reasonable runtime.
- Alpha-Lake API changes require coordinated version bumps — enforced by the `/v1/contract` capability check.

## Supersedes

- ADR-0006 (DuckDB/Parquet analytical store)
- ADR-0008 (Custom numpy indicator recurrences)
- ADR-0012 (EODHD as primary data source)
- ADR-0015 (Incremental O(1) indicator engine)
- ADR-0018 (Bootstrap + fixture bundle workflow)
- ADR-0020 (DuckDB for vault manifest)
- ADR-0025 (SEC connector SQLite cache)
- ADR-0026 (Content-addressed vault)
- ADR-0032 (Alpha-Lake sole data plane)
- ADR-0034 (LakeGateway port and adapters)

## References

- ADR-0036 (Neutral Facts in Alpha-Lake, Strategy Policy in Alpha-Quant)
- ADR-0033 (PIT reads via Clock-driven `as_of`)
- ADR-0003 (Ports-and-adapters architecture)

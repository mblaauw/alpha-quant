# ADR-0034: LakeGateway Port and Adapters

**Status:** Accepted

**Date:** 2026-06-21

## Context

The Alpha-Lake data plane (ADR-0032) requires a clean hexagonal boundary for data access. Domain code (indicators, scoring, portfolio) must not depend on how data is stored — it should call a port interface. The system needs three adapter implementations:

1. **RealLakeGateway** — reads from the production lake (local Parquet datasets, live mode).
2. **FixtureLakeGateway** — reads from pre-loaded fixture bundles for deterministic replay and CI.
3. **FakeLakeGateway** — an in-memory adapter for fast unit tests that returns canned data without I/O.

Before Alpha-Lake, there was no unified read port. Each consumer either:
- Called DuckDB's `read_parquet` directly (coupling to storage), or
- Used ad-hoc fixture-loading helpers (no standard interface for test doubles).

## Decision

**Define a `LakeGateway` port (`typing.Protocol`) with fixture-first testing.**

### Port Interface

```python
class LakeGateway(Protocol):
    def bars(self, symbol: str, as_of: date) -> pd.DataFrame: ...
    def fundamentals(self, symbol: str, as_of: date) -> dict | None: ...
    def insider_transactions(self, symbol: str, as_of: date) -> pd.DataFrame: ...
    def mentions(self, symbol: str, as_of: date) -> pd.DataFrame: ...
    def earnings_calendar(self, symbol: str, as_of: date) -> list[dict]: ...
```

The `as_of` parameter is required (per ADR-0033). All methods return data that was available on or before `as_of`.

### Adapter Implementations

| Adapter | Mode | Storage | I/O |
|---------|------|---------|-----|
| `RealLakeGateway` | Live, replay | Parquet datasets (local → S3) | Real filesystem |
| `FixtureLakeGateway` | CI, golden replay | In-memory from fixture bundles | None (pre-loaded) |
| `FakeLakeGateway` | Unit tests | In-memory dicts | None (canned) |

### Fixture-First Testing

- All golden replay tests use `FixtureLakeGateway`, which reads from fixture bundles created by the bootstrap workflow (ADR-0018).
- Unit tests use `FakeLakeGateway` to test domain logic in isolation without any I/O.
- Integration tests use `RealLakeGateway` with a temporary lake directory.

### Adapter Selection

The app layer injects the appropriate adapter at startup based on mode:
- `--replay` / `--test` → `FixtureLakeGateway`
- `--live` → `RealLakeGateway`
- Unit tests → `FakeLakeGateway`

## Consequences

### Positive

- Domain code never depends on storage internals — only on the `LakeGateway` protocol
- Three adapter implementations cover every execution mode without conditional logic in domain code
- `FakeLakeGateway` enables sub-millisecond unit tests for indicator and scoring logic
- `FixtureLakeGateway` makes golden replay deterministic (pre-loaded data, no filesystem I/O during replay)
- Swapping storage backend (Parquet → S3 → DuckDB) requires only a new adapter implementation

### Negative

- Three adapters to maintain, though each is small (~50 lines each) and the interface is stable
- The port interface must evolve carefully — adding a new read method requires updating all three adapters
- `FixtureLakeGateway` must mirror the real adapter's query semantics exactly (same filtering, same sort order) to avoid fixture-replay mismatches

## References

- ADR-0032 (Alpha-Lake as the sole data plane)
- ADR-0033 (PIT reads via Clock-driven `as_of`)
- ADR-0017 (Golden replay CI)
- ADR-0018 (Bootstrap + fixture bundle workflow)
- ADR-0003 (Ports-and-adapters architecture)

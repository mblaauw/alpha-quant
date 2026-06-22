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

**Define a `LakeGateway` port (`ABC`) with fixture-first testing.**

### Port Interface

```python
class LakeGateway(ABC):
    def bars(self, symbol: str, start: date, end: date, as_of: datetime, price_mode: str = "split_adjusted") -> list[Bar]: ...
    def latest_bar(self, symbol: str, as_of: datetime) -> Bar | None: ...
    def trading_calendar(self, start: date, end: date) -> list[TradingDay]: ...
    def fundamentals(self, symbol: str, as_of: datetime) -> FundamentalsSnapshot | None: ...
    def earnings_calendar(self, start: date, end: date, as_of: datetime) -> list[EarningsEntry]: ...
    def insider_transactions(self, symbol: str, as_of: datetime) -> list[InsiderTransaction]: ...
    def mention_counts(self, symbol: str, days: int, as_of: datetime) -> list[MentionCount]: ...
    def dataset_health(self) -> dict[str, object]: ...
    def pin_snapshot(self, snapshot_id: str | None) -> None: ...
```

The `as_of` parameter is required (per ADR-0033). All methods return data that was available on or before `as_of`. Methods return domain model objects, not raw DataFrames.

### Adapter Implementations

| Adapter | Mode | Storage | I/O |
|---------|------|---------|-----|
| `InProcessLakeGateway` | Live, replay | Parquet datasets via alpha-lake library | Local filesystem |
| `FixtureLakeGateway` | CI, golden replay | In-memory from fixture Parquet bundles | None (pre-loaded) |
| (REST variant deferred) | Future live | Alpha-Lake REST panel (not yet implemented) | Network |

### Fixture-First Testing

- All golden replay tests use `FixtureLakeGateway`, which reads from fixture bundles created by the bootstrap workflow (ADR-0018).
- Unit tests use `FixtureLakeGateway` with minimal fixture Parquet files.
- Integration tests use `InProcessLakeGateway` with a temporary lake directory.

### Adapter Selection

The app layer injects the appropriate adapter at startup based on config:
- `lake.mode = "fixture"` → `FixtureLakeGateway`
- `lake.mode = "in_process"` → `InProcessLakeGateway`

## Consequences

### Positive

- Domain code never depends on storage internals — only on the `LakeGateway` ABC
- Two adapter implementations cover every execution mode without conditional logic in domain code
- `FixtureLakeGateway` makes golden replay deterministic (pre-loaded data, no filesystem I/O during replay)
- Swapping storage backend (Parquet → S3 → DuckDB) requires only a new adapter implementation

### Negative

- Two adapters to maintain (~320 lines each), though the interface is stable
- The port interface must evolve carefully — adding a new read method requires updating both adapters
- `FixtureLakeGateway` must mirror the real adapter's query semantics exactly (same filtering, same sort order) to avoid fixture-replay mismatches

## References

- ADR-0032 (Alpha-Lake as the sole data plane)
- ADR-0033 (PIT reads via Clock-driven `as_of`)
- ADR-0017 (Golden replay CI)
- ADR-0018 (Bootstrap + fixture bundle workflow)
- ADR-0003 (Ports-and-adapters architecture)

# ADR-0032: Alpha-Lake as the Sole Data Plane

**Status:** Accepted

**Date:** 2026-06-21

## Context

Alpha-Quant originally ingested raw data through multiple independent connectors (Tiingo, EODHD, SEC EDGAR, OpenInsider, Reddit, Alpaca) that wrote directly to a content-addressed vault and then normalized into a canonical Parquet store. This design (documented in ADR-0012, ADR-0025, ADR-0026) evolved organically during P0–P2 and produced three structural problems:

1. **Connector-vault coupling.** Each connector had to manage vault writes, content hashing, compression, and manifest updates. Adding a new data source required understanding the full write path.

2. **Dual write path.** The same data flowed through connectors → vault → canonical, but the vault's content-addressed storage was never queried directly. It existed solely as an archive with no consumer.

3. **No data-plane abstraction.** Domain code (indicators, scoring, portfolio) and adapter code (connectors, stores) shared no boundary for data access. Any component could read Parquet files directly, making it impossible to swap storage backends or introduce caching without touching every consumer.

The P3.RB refinement sprint recommended replacing the vault-centric pipeline with a single data-plane abstraction — Alpha-Lake — that owns all source-data reads and writes. The vault, connectors, and canonical store are replaced by a unified Lake interface.

## Decision

**Alpha-Lake becomes the sole data plane.** All source data (bars, fundamentals, insider transactions, mentions) is ingested through Alpha-Lake and consumed through the LakeGateway port (ADR-0034).

Specific changes:

- **In-process first.** The initial implementation reads from local Parquet datasets and writes via the LakeStore adapter. This replaces the vault (ADR-0026), the SEC SQLite cache (ADR-0025), and the per-connector canonical write path.

- **REST deferred.** A REST API layer around the lake is designed but not implemented in P3.8. It will be introduced when multi-process or remote access is required (future phase).

- **Connectors become lake writers.** Connectors now produce Lake events (BarsIngested, FundamentalsIngested, etc.) rather than writing directly to the vault. The LakeStore persists these events.

- **Vault retired.** The content-addressed vault (`vault/` directory, `manifest.db`, `vault.py`) is removed. Existing vault data is migrated to the lake format once.

- **SEC SQLite cache retired.** The per-connector SEC cache (`sec_cache.db`) is replaced by the lake's dataset cache.

## Consequences

### Positive

- Single data-plane interface: all consumers read through LakeGateway, not directly from Parquet files
- Connectors are simpler: they produce events instead of managing vault storage
- The vault archive is eliminated — no dual-write, no dead code path
- Backend swap: swapping local Parquet for S3/MinIO requires changing only the Lake adapter
- Cache consistency: SEC ticker map caching moves from a per-connector SQLite DB to the lake's dataset cache

### Negative

- Migration: existing vault data must be migrated to the lake format (one-time script)
- The in-process lake writer is a single point of write coordination — acceptable for the daily batch pipeline
- REST API is deferred: multi-process or remote access is not yet supported

## References

- Supersedes ADR-0012 (EODHD as primary data source)
- Supersedes ADR-0025 (SEC connector SQLite cache)
- Supersedes ADR-0026 (Content-addressed vault)
- ADR-0033 (PIT reads via Clock-driven `as_of`)
- ADR-0034 (LakeGateway port and adapters)
- ADR-0028 (Clock virtualization for determinism)

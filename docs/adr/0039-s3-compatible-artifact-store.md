# ADR-0039: S3-Compatible Artifact Store for Decision Evidence

**Status:** Superseded — decision evidence stored as JSON rows in PostgreSQL, not in S3.

**Date:** 2026-06-26

## Context

Every decision Alpha-Quant makes is a candidate for post-hoc analysis: why was a particular candidate promoted or blocked? What was the decision context (prices, indicators, fundamentals) at that moment?

Storing this evidence in the PostgreSQL operational store is possible but undesirable:

1. **Blob storage in PostgreSQL**: JSON decision snapshots are large and infrequently queried. Storing them in PostgreSQL bloats the operational database and slows backups.
2. **Query pattern**: Decision evidence is read during post-hoc analysis and debugging, not during live decision cycles. It belongs in a cheaper, slower storage tier.
3. **Immutable artifacts**: Once a decision is made, the evidence supporting it is immutable. An append/read-only store is the natural fit.

The decision cycle produces approximately one artifact per symbol per run day — roughly 100–500 KB of JSON per artifact. With a universe of 100–500 symbols, this is 10–250 MB per run day.

## Decision

**Store decision evidence artifacts in S3-compatible object storage.** Each artifact is a JSON document containing the full decision context for one symbol at one decision point.

### Bucket naming

- Bucket name: `alpha-quant-artifacts`
- Key pattern: `<run_id>/<symbol>/<decision_id>.json`
- Separating by `run_id` enables S3 lifecycle policies for cost management.

### Artifact contents

Each artifact is a JSON document with:

- `run_id` — the decision run identifier
- `symbol` — the symbol evaluated
- `as_of` — the decision timestamp
- `snapshot_id` — the Alpha-Lake snapshot used (if available)
- `observations` — the full `SymbolObservations` data at decision time
- `candidate` — the `CandidateEvaluation` result (scores, gates, block reason)
- `decision` — the final `Decision` (enter/exit/skip) with confidence and reasons

### Verification

Each artifact carries SHA-256 checksum metadata at the S3 object level. The artifact store can verify artifact integrity on read.

### Client

The `S3ArtifactStore` adapter uses `boto3` with lazy import. It supports any S3-compatible endpoint (AWS S3, MinIO, Cloudflare R2, DigitalOcean Spaces) via the `endpoint_url` parameter.

### Write path

Artifacts are written during the pipeline run, after each candidate evaluation. The write is fire-and-forget — a failure to write an artifact does not halt the run. Failed writes are logged as warnings.

### Read path

Artifacts are read during post-hoc analysis via the CLI or a future dashboard. No artifact read occurs during the live decision cycle.

## Consequences

### Positive

- Decision evidence is durable, immutable, and independently queryable.
- PostgreSQL operational store stays lean (no blob storage).
- S3 lifecycle policies can archive or expire old artifacts automatically.
- Standard S3 tooling works for analysis (AWS CLI, `boto3`, S3 browser).

### Negative

- Additional operational dependency (S3-compatible endpoint).
- Artifact writes add latency to the run cycle (mitigated by fire-and-forget).
- No built-in cross-region replication — artifacts are in a single bucket.
- SHA-256 verification adds read overhead.

## References

- ADR-0037 (PostgreSQL operational system of record)
- ADR-0038 (Append-only ledger with rebuildable projections)
- `src/alpha_quant/adapters/artifacts/s3_artifact_store.py`
- `src/alpha_quant/ports/artifact_store.py`

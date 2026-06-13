# ADR-0026: Vault Design — Append-Only Raw Data Storage

## Status

Accepted

## Date

2026-06-12

## Context

The system needs a durable, append-only archive of raw API responses (bars, fundamentals, insider transactions, mentions) from all data connectors. This archive ("the vault") serves two purposes:

1. **Reproducibility** — Given a vault snapshot from date X, the pipeline can replay the exact same data that was available on that date.
2. **Incremental backfill** — New connectors or indicator changes can be tested against historical data without re-fetching.

The vault stores data in its raw wire format so that normalization and processing logic can evolve independently of the raw data.

## Decision Drivers

- Append-only: raw data must never be modified after writing
- Content-addressed: identical responses produce identical file names, enabling deduplication
- Self-describing: the vault must be usable without external metadata (directory structure encodes source and date)
- Fast replay: O(log n) lookup by source, date range, or symbol
- Compression: JSON text must be compressed for storage efficiency

## Considered Options

- **Option A: Zstd-compressed JSON files in date-partitioned directory tree + DuckDB manifest** — Chosen.
- **Option B: Parquet-only** — Raw data must be parsed before storage, losing the original wire format.
- **Option C: Single SQLite file with blob columns** — Single file but no filesystem-level partitioning; requires SQL for all queries.
- **Option D: Object storage (S3/GCS) with metadata DB** — Better scalability but over-engineered for single-machine deployment.
- **Option E: No vault (store only normalized data)** — Cannot replay original API responses; normalization bugs cannot be retroactively fixed.

## Decision Outcome

Chosen option: **Option A — Zstd-compressed JSON files in a date-partitioned directory tree, indexed by a DuckDB manifest with content hashes.**

### Directory Structure

```
vault/
  eodhd/
    eod/
      2026/
        06/
          11/
            abc1234f.zst   # 2026-06-11 09:30 fetch
            5678abcd.zst   # 2026-06-11 10:00 fetch
    fundamentals/
      2026/06/11/...
  alpaca/
    bars/
      2026/06/11/...
  openinsider/
    2026/06/11/...
  reddit/
    2026/06/11/...
  sec/
    2026/06/11/...
```

### File Naming

- Each fetch produces one `.zst` file
- Filename is the first 8 hex chars of SHA256(content) — content-addressed
- This guarantees file-level deduplication: re-fetching identical data produces the same filename

### Compression

- Zstd with default compression level (3)
- Chosen over gzip for faster decompression (important during replay) and better compression ratios on JSON text
- Python's `zstandard` library provides bindings

### Manifest Schema (DuckDB)

The manifest (stored as a DuckDB database file `vault/manifest.db`) tracks every fetch:

```sql
CREATE TABLE manifest (
  fetch_id VARCHAR PRIMARY KEY,
  source VARCHAR NOT NULL,
  dataset VARCHAR NOT NULL,
  symbol VARCHAR,
  fetch_date DATE NOT NULL,
  fetch_time TIMESTAMP NOT NULL,
  path VARCHAR NOT NULL,
  content_hash VARCHAR NOT NULL,
  byte_size BIGINT NOT NULL,
  status VARCHAR NOT NULL DEFAULT 'ok'
);
```

- `fetch_id` = SHA256(source + dataset + symbol + timestamp)[:16]
- `content_hash` = SHA256(file content)[:16] (matches filename)
- `status` = 'ok' | 'stale' | 'corrupt'

### Positive Consequences

- **Append-only immutability** — Raw data is never modified after writing. Normalization logic can evolve independently.
- **Content-addressed deduplication** — Identical API responses from different days or connectors share one file.
- **Fast replay** — DuckDB manifest enables O(log n) lookup of fetches by date range, source, or symbol.
- **Independent of schema** — Raw JSON preserves all fields, even those not yet consumed by normalization.

### Negative Consequences

- **Storage growth** — Raw JSON + compression is larger than normalized parquet. Estimated ~3x storage for raw vs canonical.
- **Two DuckDB databases** — The vault manifest is a separate DuckDB file from the state database. Managing two DuckDB instances adds minor operational complexity.
- **No built-in retention** — Old data is never deleted. A separate purge/vacuum process would need to be designed for storage management in long-running deployments.
- **8-char content hash vulnerable to birthday bound** — At ~65k files, collision probability is ~50%. A future enhancement should increase this to 16 hex chars.

## References

- ADR-0006: Use DuckDB + Parquet for Analytical Store
- ADR-0020: Use DuckDB for Vault Manifest
- ADR-0021: Use DuckDB for Both Analytical and Transactional State
- `alpha_quant/app/vault.py`
- `alpha_quant/app/bootstrap.py`

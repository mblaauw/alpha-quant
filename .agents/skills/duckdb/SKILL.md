---
name: duckdb
description: DuckDB queries for Alpha-Quant's analytical store and state database. Use when you need to inspect state.db, query canonical Parquet data, debug pipeline state, or explore the vault manifest.
---

# DuckDB for Alpha-Quant

Alpha-Quant uses DuckDB for both transactional state and analytical storage.

## State Database

The main state database is at `data/state.db`. Tables include:
- `decisions` — Daily trading decisions per candidate
- `orders` — Generated orders
- `fills` — Executed fills
- `positions` — Current and historical positions
- `equity_curves` — Daily equity snapshots
- `events` — Domain event log
- `indicator_state` — Technical indicator state
- `catalog` — Data catalog entries

```bash
duckdb data/state.db -c "SELECT * FROM information_schema.tables;"
duckdb data/state.db -c "SELECT * FROM events ORDER BY timestamp DESC LIMIT 20;"
duckdb data/state.db -c "SELECT date, equity FROM equity_curves ORDER BY date;"
```

## Canonical Store (Parquet)

Analytical data is stored as date-partitioned Parquet in `data/canonical/`:
- `bars/` — Daily OHLCV bars
- `fundamentals/` — Fundamental snapshots
- `insider/` — Insider transaction clusters
- `mentions/` — Reddit mention counts

```bash
duckdb -c "SELECT * FROM 'data/canonical/bars/**/*.parquet' LIMIT 10;"
duckdb -c "SELECT symbol, COUNT(*) FROM 'data/canonical/bars/**/*.parquet' GROUP BY symbol;"
```

## Vault Manifest

Raw API payloads are in `vault/` with manifest at `vault/manifest.db`:
```bash
duckdb vault/manifest.db -c "SELECT * FROM manifest ORDER BY ingested_at DESC LIMIT 10;"
```

## Python Access

From Python via the project's store adapter:

```python
import duckdb
conn = duckdb.connect("data/state.db")
rows = conn.execute("SELECT * FROM equity_curves").fetchall()
```

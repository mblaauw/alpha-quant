# ADR-0025: Use SQLite Cache for SEC Connector

- **Status:** Accepted
- **Date:** 2026-06-12
- **Deciders:** mich

## Context

The SEC connector (`adapters/real/sec_connector.py`) fetches the full EDGAR ticker-to-CIK mapping via `https://www.sec.gov/files/company_tickers_exchange.json`. This mapping is required to resolve ticker symbols to CIK numbers before querying individual company filings. The API response is large (~10MB) and the SEC enforces a strict 1 request/second rate limit. Re-fetching the mapping on every pipeline run would be wasteful and slow.

Several options were considered for caching this mapping.

## Decision

Use a per-connector SQLite database (`sec_cache.db`) with a 24-hour TTL to cache the ticker-to-CIK mapping. The cache is stored alongside the vault in the system data directory.

### Rationale

1. **SEC-specific concern** — This cache is unique to the SEC connector; no other connector in the system has a similar caching need. A generic caching layer would be over-engineering.

2. **SQLite over DuckDB** — The mapping is a simple key-value lookup (ticker → CIK). SQLite's `CREATE TABLE ticker_map (ticker TEXT PRIMARY KEY, cik TEXT, name TEXT)` is the simplest possible schema. Using DuckDB for this single-purpose cache would create unnecessary coupling between the SEC connector and the main analytical store.

3. **TTL over staleness-based refresh** — The SEC exchange ticker file rarely changes (updates monthly at most). A 24-hour TTL is conservative and avoids the complexity of tracking individual record staleness.

4. **1 req/s rate limit** — The connector already respects the SEC's rate limit. The cache simply avoids unnecessary fetches within a single day's pipeline run.

### Implementation

- Cache file: `{data_dir}/sec_cache.db`
- Schema: `CREATE TABLE IF NOT EXISTS ticker_map (ticker TEXT PRIMARY KEY, cik TEXT, name TEXT, cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)`
- TTL check: `SELECT MAX(cached_at) FROM ticker_map` — if >24h old, re-fetch
- Cache-first: Read from cache before hitting the API, write to cache after successful API fetch

## Consequences

### Positive
- Eliminates unnecessary API calls to the SEC within a single day's pipeline run
- Respects SEC's 1 req/s rate limit by only fetching once per 24 hours
- Simple implementation with no shared infrastructure dependencies
- Independent of the main DuckDB store — can be cleared separately without affecting other data

### Negative
- Introduces a second embedded database (SQLite + DuckDB) in the system architecture
- Cache directory location must be configurable via the application config
- If the cache becomes stale (>24h) and the SEC API is briefly unavailable, the pipeline must handle the degraded state gracefully

## References

- ADR-0006: Use DuckDB + Parquet for Analytical Store
- ADR-0021: Use DuckDB for Both Analytical and Transactional State
- `adapters/real/sec_connector.py`
- `https://www.sec.gov/files/company_tickers_exchange.json`

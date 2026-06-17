# ADR-0012: Use EODHD as the Primary Market Data Source

## Status

Deprecated

*Deprecated — EODHD has been replaced by **Tiingo** (daily OHLCV bars) and **SEC EDGAR** (fundamentals). EODHD remains available as a disabled fallback connector but is no longer the primary data source.*

## Date

2026-06-10

## Context

Alpha-Quant requires daily OHLCV bars, fundamentals snapshots (OCF, D/E, accruals, revenue), and earnings calendar data for 50+ US equities. The data must be reliable, well-documented, and cost-effective for a retail-focused project (< $100K AUM).

DESIGN.md §3.2 defines 5 data connectors, with EODHD as the primary source for bars and fundamentals.

## Decision Drivers

- Single source for bars, fundamentals, and earnings — minimizes connector surface area
- API key authentication (no complex OAuth)
- Reliable uptime for daily 17:30 ET scheduled fetch
- Cost: budget-friendly for the pre-revenue / retail phase
- Batch endpoint for efficient daily delta updates

## Considered Options

- **Option A: EODHD** — Bars, fundamentals, earnings calendar in one API; batch endpoint; free tier available; paid plans from $40/month
- **Option B: Polygon.io** — Excellent data quality, but bars and fundamentals are separate APIs (different billing); starts at $200/month
- **Option C: Alpha Vantage** — Free tier (5 calls/min, 500/day), but rate limits are severe for 50 symbols; no fundamentals in free tier
- **Option D: Yahoo Finance (yfinance)** — Free, but unofficial; no SLA, frequently broken, no fundamentals API; violates the deterministic data contract (I4)

## Decision Outcome

Chosen option: **Option A — EODHD**.

Rationale:
1. Combined bars + fundamentals + earnings in one API — minimizes connector count and failure surface
2. Batch endpoint (`/eod-bulk-last-day/{exchange}`) enables efficient daily delta fetches for 50 symbols
3. Historical data depth: up to 20+ years of daily data for backtesting (required by DESIGN §14)
4. Cost: $40/month paid plan is affordable for the project; free tier sufficient for initial development
5. Documentation quality: clear API reference, active support

### Positive Consequences

- One connector to maintain for the three most important data categories
- Batch endpoint means 1 API call covers all 50 symbols for daily updates
- Historical depth enables 10-year backtests with the same data source
- API key authentication is simple (no OAuth refresh token management)

### Negative Consequences

- Dependent on a single provider for fundamentals data (M4 gate depends on fundamentals accuracy)
- EODHD's fundamentals coverage is not as deep as Bloomberg terminals (but sufficient for the quality gate — OCF, D/E, accruals)
- If EODHD changes pricing or removes the fundamentals endpoint, the system degrades gracefully (M4 pass-with-SOURCE_DEGRADED event)

## References

- DESIGN.md §3.2 (Connectors — EODHD), §3.8 (Library decisions)
- RAD §4 (System Context — EODHD)
- C4 System Context diagram: `docs/architecture/views/systemContext.png`
- EODHD API documentation: https://eodhd.com/api

## Replacement

EODHD was replaced by **Tiingo** (daily OHLCV bars — free tier, reliable) and **SEC EDGAR CompanyFacts** (fundamentals — free, direct source). The system now has two primary data sources instead of one:
- **Tiingo** — Daily bars (primary), earnings calendar
- **SEC EDGAR** — Fundamentals snapshots (OCF, D/E, accruals) via `sec_fundamentals_connector.py`

EODHD's `eodhd_connector.py` remains in the codebase as a disabled fallback but is no longer used in the default pipeline configuration. See ADR-0025 (SEC SQLite Cache) and the multi-adapter framework for the current adapter architecture.

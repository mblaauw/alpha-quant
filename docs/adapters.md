# Adapter Reference

## Port → Implementation Matrix

| Port                  | Interface                                                         | Real Adapter                                 | Fake Adapter         |
|-----------------------|-------------------------------------------------------------------|----------------------------------------------|----------------------|
| **MarketData**        | `daily_bars`, `latest_quote`, `trading_calendar`                  | TiingoConnector, AlpacaConnector (redundant) | FixtureMarketData    |
| **Fundamentals**      | `snapshot`, `earnings_calendar`                                   | SECFundamentalsConnector, EODHDConnector     | FixtureFundamentals  |
| **InsiderFeed**       | `cluster_transactions`, `recent_clusters`                         | OpenInsiderConnector                         | FixtureInsiderFeed   |
| **SentimentFeed**     | `mention_counts`, `baseline`                                      | RedditSentimentConnector                     | FixtureSentimentFeed |
| **Clock**             | `now`, `today`, `market_date`                                     | SystemClock                                  | VirtualClock         |
| **Broker**            | `submit_order`, `cancel_order`, `portfolio`, `positions`, `fills` | AlpacaBroker                                 | FakeBroker           |
| **EventSink**         | `emit`, `query`                                                   | DuckDBEventSink / SqliteEventSink            | FakeEventSink        |
| **LLM**               | `explain`, `generate_card`                                        | OpenAILikeLLM                                | CannedLLM            |
| **Store** (composite) | bar/order/position/event/indicator/journal/admin stores           | *(none — CanonicalStore is app-layer)*       | FixtureStore         |
| *(no port)*           | `ticker_map`, `check_connection`                                  | SECConnector                                 | —                    |

---

## Category: Bars (Daily OHLCV)

| Adapter             | Source                       | Auth          | Adj Close          | Status                                      |
|---------------------|------------------------------|---------------|--------------------|---------------------------------------------|
| **TiingoConnector** | `api.tiingo.com`             | `?token=`     | ✅ `adjClose`       | **Active** — free tier, ~500-1000 calls/hr  |
| AlpacaConnector     | `data.alpaca.markets`        | key+secret    | ❌ (close only)     | **Redundant** — not wired in factory        |
| EODHDConnector      | `eodhd.com/api`              | `?api_token=` | ✅ `adjusted_close` | **Unused for bars** — used for fundamentals |
| FixtureMarketData   | `fixtures/v1/bars/*.parquet` | —             | ✅                  | **Test** — deterministic replay             |

## Category: Fundamentals

| Adapter                     | Source                              | Auth       | Fields                                                      | Status                                    |
|-----------------------------|-------------------------------------|------------|-------------------------------------------------------------|-------------------------------------------|
| **SECFundamentalsConnector** | `data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json` | User-Agent | EPS TTM, revenue, NI, OCF, debt, equity, liabilities, accruals | **Active** — free, no API key required   |
| EODHDConnector              | `eodhd.com/api`                     | `?api_token=` | mcap, PE, EPS, D/E, OCF, accruals, revenue, sector/industry | **Fallback** — needs valid API key (403) |
| FixtureFundamentals         | `fixtures/v1/fundamentals/*.parquet` | —          | Subset (mcap, PE, EPS, sector)                              | **Test**                                  |

### SEC XBRL → FundamentalsSnapshot mapping

| Snapshot field | US-GAAP concept(s) | Method |
|---|---|---|
| `eps_ttm` | `EarningsPerShareDiluted` | `_sum_quarterly` — sum last 4 Q entries |
| `net_income` | `NetIncomeLoss` | `_latest_annual` — latest `fp=FY` |
| `revenue` | `Revenues` → `RevenueFromContractWithCustomerExcludingAssessedTax` | Fallback chain |
| `operating_cash_flow` | `NetCashProvidedByOperatingActivities` → `...ContinuingOperations` → `NetCashProvidedByUsedInOperatingActivities` | Fallback chain (3 levels) |
| `total_debt` | `LongTermDebtNoncurrent` + `ShortTermBorrowings` | `_sum_annual` — sum both |
| `total_equity` | `StockholdersEquity` | `_latest_annual` |
| `total_liabilities` | `Liabilities` | `_latest_annual` |
| `accruals` | computed: `net_income - operating_cash_flow` | — |
| `market_cap`, `pe_ratio`, etc. | Not in CompanyFacts | `None` |

## Category: Insider Transactions

| Adapter | Source | Auth | Coverage | Status |
|---|---|---|---|---|
| **OpenInsiderConnector** | `openinsider.com` (HTML scrape) | None | Last 30 days, max 1000 rows | **Active** — slow (0.33 tps), fragile to HTML changes |
| FixtureInsiderFeed | `fixtures/v1/insider_tx/*.parquet` | — | Deterministic | **Test** — `recent_clusters()` returns `[]` |

## Category: Sentiment / Mentions

| Adapter | Source | Auth | Coverage | Status |
|---|---|---|---|---|
| **RedditSentimentConnector** | `reddit.com/r/wallstreetbets+stocks` | None | ~100 most recent posts per subreddit | **Active** — slow (0.167 tps), Reddit now blocks unauthenticated JSON |
| FixtureSentimentFeed | `fixtures/v1/mentions/*.parquet` | — | Deterministic | **Test** |

---

## Shared Infrastructure

| Component | File | Role |
|---|---|---|
| **BaseConnector** | `adapters/real/base_connector.py` | HTTP client + token-bucket rate limiter + tenacity retry (5 attempts, 429-aware backoff) + vault lineage |
| **TokenBucket** | `adapters/real/token_bucket.py` | Thread-safe rate limiter used by every real connector |
| **FetchResult** | `adapters/real/base_connector.py` | Dataclass pairing `httpx.Response` with optional `fetch_id` for data lineage |

---

## Multi-Adapter Fundamentals

The fundamentals port supports **multiple concurrent adapters**. When more than one source
is enabled in `[adapters.fundamentals]`, each adapter's data is stored tagged with its
`adapter` column (e.g., `sec_edgar`, `eodhd`). The `primary` setting controls which
adapter is used for the live decision pipeline (via `CompositeFundamentals.snapshot()`).

```toml
[adapters.fundamentals]
primary = "sec_edgar"

[adapters.fundamentals.sources.sec_edgar]
enabled = true

[adapters.fundamentals.sources.eodhd]
enabled = false
```

---

## Wiring (factory.py → live mode)

```
create_market_data     → TiingoConnector
create_fundamentals    → SECFundamentalsConnector | CompositeFundamentals (multi)
create_insider_feed    → OpenInsiderConnector
create_sentiment_feed  → RedditSentimentConnector
create_clock           → SystemClock
create_broker          → AlpacaBroker
create_llm             → OpenAILikeLLM
create_event_sink      → DuckDBEventSink
create_store           → CanonicalStore
create_sec_connector   → SECConnector
```

---

## Gaps & Known Limitations

- **SECFundamentalsConnector `earnings_calendar()`** returns `[]` — SEC provides actuals only; no estimates API
- **SEC XBRL taxonomy**: US-GAAP only; IFRS filers (e.g., ASML) may return `None` for some fields
- **SEC revenue concept varies**: different companies use different XBRL tags; `Revenues` + `RevenueFromContractWithCustomerExcludingAssessedTax` covers most US filers
- **Tiingo `latest_quote`** uses last close as bid/ask proxy (no real quote endpoint on free tier)
- **Tiingo `trading_calendar`** is weekday-only — no market holiday awareness
- **AlpacaBroker `fills()`** returns `[]` (not implemented)
- **OpenInsider** HTML scraping is fragile; rate limited to 0.33 tps
- **Reddit** now requires authentication for JSON access (403 on public endpoint)
- **EODHD fundamentals** kept as configurable fallback but requires valid API key (currently 403)
- **FixtureInsiderFeed `recent_clusters()`** returns `[]` unconditionally

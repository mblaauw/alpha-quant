# Adapter Reference

## Port → Implementation Matrix

| Port                  | Interface                                                         | Real Adapter                 | Fake Adapter          |
|-----------------------|-------------------------------------------------------------------|------------------------------|-----------------------|
| **MarketData**        | `daily_bars`, `latest_quote`, `trading_calendar`                  | LakeMarketData               | FixtureLakeGateway    |
| **Fundamentals**      | `snapshot`, `earnings_calendar`                                   | LakeFundamentals             | FixtureLakeGateway    |
| **InsiderFeed**       | `cluster_transactions`, `recent_clusters`                         | LakeInsiderFeed              | FixtureLakeGateway    |
| **SentimentFeed**     | `mention_counts`, `baseline`                                      | LakeSentimentFeed            | FixtureLakeGateway    |
| **Clock**             | `now`, `today`, `market_date`                                     | SystemClock                  | VirtualClock          |
| **Broker**            | `submit_order`, `cancel_order`, `portfolio`, `positions`, `fills` | AlpacaBroker                 | FakeBroker            |
| **EventSink**         | `emit`, `query`                                                   | DuckDBEventSink              | FakeEventSink         |
| **LLM**               | `explain`, `generate_card`                                        | OpenAILikeLLM                | CannedLLM             |
| **Store** (composite) | bar/order/position/event/indicator/journal/admin stores           | CanonicalStore (DuckDB)      | FixtureStore          |

---

## LakeGateway — Data Plane Port

All market, fundamental, insider, and sentiment data flows through a single port: `LakeGateway` (`ports/lake.py`). Every read is a point-in-time (PIT) query against Alpha-Lake, clock-driven by `as_of` — the pipeline never ingests raw data directly.

| Method | Returns | Purpose |
|--------|---------|---------|
| `bars(symbol, start, end, as_of, price_mode)` | `list[Bar]` | Daily OHLCV bars with split/dividend adjustment |
| `latest_bar(symbol, as_of)` | `Bar \| None` | Most recent bar available as of a timestamp |
| `trading_calendar(start, end)` | `list[TradingDay]` | Market-open calendar |
| `fundamentals(symbol, as_of)` | `FundamentalsSnapshot \| None` | Latest fundamentals snapshot |
| `earnings_calendar(start, end, as_of)` | `list[EarningsEntry]` | Earnings report dates |
| `insider_transactions(symbol, as_of)` | `list[InsiderTransaction]` | Insider filings |
| `mention_counts(symbol, days, as_of)` | `list[MentionCount]` | Social-media mention counts |
| `dataset_health()` | `dict[str, object]` | Per-dataset staleness and availability |
| `pin_snapshot(snapshot_id)` | `None` | Pin a specific lake snapshot for replay |

### Adapter: InProcessLakeGateway

`adapters/real/lake_inprocess.py` — imports the `alpha_lake` library in-process, connecting to the lake's DuckDB catalog directly. Used in live mode.

- Resolves symbols to security IDs via `alpha_lake.security_master`
- Reads PIT-panel data via `alpha_lake.serving.read_bars_adjusted()`
- Queries per-dataset views (`fundamentals`, `earnings_calendar`, `insider_tx`, `attention_metrics`) with `available_at <= as_of` filtering
- Returns domain-typed models with `adapter="alpha_lake"` lineage tag

### Adapter: FixtureLakeGateway

`adapters/fake/lake_fixture.py` — reads fixture parquet files shaped like lake views, with PIT visibility filtering (`available_at <= as_of`). Used in fixture/replay/test mode.

- Reads `.parquet` files from `fixtures/{version}/lake/` or fixture root
- Filters rows by `available_at` for deterministic PIT replay
- Supports `pin_snapshot()` for snapshot-bound replays
- Returns domain-typed models with `adapter="alpha_lake_fixture"` lineage tag

### REST mode (deferred)

`RestLakeGateway` is sketched in `factory.py` but raises `NotImplementedError`. It will be implemented when Alpha-Lake deploys PIT-serving panels over REST.

---

## Lake Adapters (Port Wrappers)

The `LakeMarketData`, `LakeFundamentals`, `LakeInsiderFeed`, and `LakeSentimentFeed` classes in `adapters/real/lake_data.py` wrap `LakeGateway` to implement the individual domain port interfaces (`MarketData`, `Fundamentals`, `InsiderFeed`, `SentimentFeed`). Each one delegates to the lake with `as_of=self._clock.now()`.

---

## Broker

| Adapter | Source | Auth | Status |
|---------|--------|------|--------|
| **AlpacaBroker** | `alpaca-py` trading SDK | key+secret | **Inactive in v1** — live execution out of scope; wired but not used |
| FakeBroker | In-memory | — | **Test** — deterministic fills for replay/backtest |

---

## LLM

| Adapter | Source | Auth | Status |
|---------|--------|------|--------|
| **OpenAILikeLLM** | OpenAI-compatible API (OpenAI, OpenRouter) | `api_key` | **Active** — explainer only, never in decision path |
| CannedLLM | Static templates | — | **Test** — deterministic LLM responses |

---

## Wiring (factory.py → live mode)

```
create_lake_gateway    → FixtureLakeGateway / InProcessLakeGateway
create_market_data     → LakeMarketData(lake_gateway, clock)
create_fundamentals    → LakeFundamentals(lake_gateway, clock)
create_insider_feed    → LakeInsiderFeed(lake_gateway, clock)
create_sentiment_feed  → LakeSentimentFeed(lake_gateway, clock)
create_clock           → SystemClock
create_broker          → AlpacaBroker
create_llm             → OpenAILikeLLM
create_event_sink      → DuckDBEventSink
create_store           → CanonicalStore
```

---

## Gaps & Known Limitations

- **SEC XBRL taxonomy**: US-GAAP only; IFRS filers (e.g., ASML) may return `None` for some fields
- **AlpacaBroker `fills()`** returns `[]` (not implemented)
- **RestLakeGateway** deferred until Alpha-Lake exposes PIT panels over REST
- **Alpha-Lake data freshness**: depends on the lake's ingestion schedule; gap between source publication and lake availability creates a natural 1-day latency

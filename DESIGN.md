# Alpha-Quant — Implementation-Ready Design (v1.2)

Deterministic, daily-cadence, long-only equity system with an **internal paper-trading engine** — no broker dependency. Alpaca is an informational data source only. LLM is explainer/educator only — never in the decision path. Ports-and-adapters architecture: pure domain core; adapters for data, LLM, storage; virtualized clock; fixture/replay harness; shadow ablation books; append-only event log; narration/education layer.

**v1.2 changes:** Alpaca demoted to data-only (§3); execution is now a fully internal paper engine (§9) — reconciliation removed, stop semantics defined against daily bars; bootstrap universe = 50 configurable symbols (§3.7); the data layer is now a fully designed subsystem with tool and library decisions (§3); phases and invariants revised.

---

## 0. Scope and non-goals

**In scope:** US liquid equities, end-of-day signals, weekly rebalance + daily risk checks, internal paper portfolio + shadow ablation books, full decision lineage, user education.

**Non-goals (v1):** live brokerage execution (the `broker` port and `FakeBroker`/`AlpacaBroker` adapters exist, but live execution is out of scope — see §9.4), intraday trading, options/derivatives, shorting, ML models, multi-agent coordination, LLM-computed numbers anywhere.

---

## 1. Architecture overview

Three execution realities, one domain core, one fill model:

```
            ┌──────────────── domain core (pure functions) ───────────────┐
            │   gates · scores · ranking · sizing · risk · fill model     │
            └──────┬──────────────────────┬─────────────────────┬─────────┘
                   │                      │                     │
              BACKTEST                 REPLAY              PAPER (primary)
           historical bars       fixture data, full     live data, internal
           research speed        DAG, virtual clock     fills — THE portfolio
                                                        + shadow ablation books
```

```
src/
├── domain/                      # pure functions, no I/O (§1 rationale)
│   ├── __init__.py              # re-exports models + events
│   ├── models.py                # all pydantic data models (frozen)
│   ├── events.py                # 20 discriminated domain event types (plus BaseDomainEvent base)
│   ├── normalize.py             # boundary parsing: bytes → pydantic models
│   ├── validate.py              # quality gates → QUARANTINE/DATA_HALT
│   ├── derive.py                # incremental O(1) indicator engine (numpy)
│   ├── universe.py              # M1 universe selection
│   └── exceptions.py            # AlphaQuantError, DataNormalizationError
├── ports/                       # ABC interfaces for all external dependencies
│   ├── clock.py                 # injected clock abstraction; most consumers use it, a few direct reads remain (tracked)
│   ├── market_data.py  fundamentals.py  insider_feed.py  sentiment_feed.py
│   ├── llm.py  store.py  event_sink.py
│   └── broker.py                # port interface; FakeBroker and AlpacaBroker adapters exist, live execution out of v1 scope (§9.4)
├── adapters/
│   ├── real/                    # production implementations
│   │   ├── clock.py             # SystemClock — wraps datetime.now(UTC)
│   │   ├── base_connector.py    # shared HTTP: httpx, tenacity retry, token-bucket, vault
│   │   ├── token_bucket.py      # thread-safe rate limiter
│   │   ├── event_sink.py        # SqliteEventSink (secondary; primary event persistence is through CanonicalStore/DuckDB)
│   │   ├── eodhd_connector.py   # EODHD: bars, fundamentals, earnings
│   │   ├── alpaca_connector.py  # Alpaca Data API: quotes, calendar, latest bar
│   │   ├── sec_connector.py     # SEC EDGAR: ticker → CIK mapping
│   │   ├── openinsider_connector.py  # OpenInsider HTML scraping
│   │   └── reddit_sentiment_connector.py  # Reddit public JSON
│   └── fake/                    # test/fixture implementations
│       ├── virtual_clock.py     # deterministic clock for replay/backtest
│       ├── fake_event_sink.py   # in-memory event store
│       ├── canned_llm.py        # static template responses
│       ├── fixture_market_data.py    # bars from fixture parquet
│       ├── fixture_fundamentals.py   # snapshots from fixture data
│       ├── fixture_insider_feed.py   # insider data from fixture
│       ├── fixture_sentiment_feed.py # mention counts from fixture
│       └── fixture_store.py         # in-memory store for test isolation
├── app/                         # application wiring + infrastructure
│   ├── __init__.py              # CLI entry point (argparse)
│   ├── _loop.py                 # shared decision-loop helpers
│   ├── alerts.py                # alert generation
│   ├── backtest.py              # historical backtest engine
│   ├── backup.py                # backup utilities
│   ├── bootstrap.py             # fixture generation (deterministic)
│   ├── catalog.py               # fixture integrity verification
│   ├── config.py                # pydantic-settings + TOML loading
│   ├── dashboard.py             # Streamlit dashboard
│   ├── factory.py               # dependency injection factory
│   ├── fixtures.py              # freeze_bundle: parquet + manifest writer
│   ├── halt.py                  # halt file management
│   ├── paper.py                 # paper trading engine
│   ├── pipeline.py              # main daily pipeline
│   ├── replay.py                # golden replay harness
│   ├── scheduler.py             # APScheduler-based daily scheduling
│   ├── vault.py                 # append-only zstd-compressed raw payload archive
│   └── store/                   # DuckDB-backed state + analytical store
│       ├── __init__.py          # re-exports
│       ├── admin_store.py       # run metadata, config snapshots
│       ├── bar_store.py         # bar data access
│       ├── canonical.py         # parquet-backed canonical store
│       ├── decision_store.py    # decision records
│       ├── event_store.py       # event log access
│       ├── indicator_store.py   # indicator state access
│       ├── journal_store.py     # journal entries
│       ├── order_store.py       # order persistence
│       ├── position_store.py    # position persistence
│       ├── schema.py            # SQL schema definitions
│       └── state.py             # CanonicalStore composite (inherits all mixins)
├── tests/                       # test suite
│   ├── unit/                    # unit tests (pure domain functions)
│   └── integration/             # integration tests (adapter contracts)
├── fixtures/                    # versioned bootstrap dataset (§3.7)
│   └── golden/                  # golden replay outputs for CI
├── docs/
│   ├── adr/                     # architecture decision records
│   ├── architecture/            # C4 diagrams (LikeC4 DSL)
│   └── spike-*.md               # evaluation spike reports
├── config.toml                  # config template (secrets in config.local.toml)
└── config.local.toml.example    # local override template
```

**Rationale for domain/ layout:** `normalize.py`, `validate.py`, and `derive.py` live in `domain/` because they are pure functions with no I/O — they take data and return data. Normalization is boundary parsing (HTTP response bytes → pydantic models), but the parsing itself has no adapter dependency. This keeps the domain core complete (all data transformations are together) while ports and adapters remain separate in their own layers.

**Rules:** `domain/` imports nothing from `adapters/`. Every connector has a fixture-backed fake twin on the same port. The pipeline never knows which reality it runs in.

---

## 2. Configuration

```toml
[bootstrap]
symbols = ["AAPL","MSFT","NVDA", "...47 more"]   # 50 initial, fully configurable
history_years = 3
include_benchmarks = ["SPY", "^VIX"]

[data]
indicator_state = true
staleness_halt_hours = 30
fixture_version = "v1"

[universe]
min_price = 5.0
min_adv_usd = 5_000_000
index_base = "sp500_plus_midcap400"   # bootstrap list is the dev subset of this

[portfolio]
max_positions = 8
max_position_pct = 0.15
max_gross_exposure = 0.80
risk_per_trade_pct = 0.01
max_sector_positions = 2

[paper]
starting_equity = 100000
slippage_bps = 5
spread_model = "half_spread_estimate"

[risk]
stop_atr_mult = 2.0
trail_after_r = 1.0
partial_take_at_r = 2.0
time_stop_days = 30
dd_ladder = [[0.10, 0.5], [0.15, 0.0]]
daily_loss_halt_pct = 0.03

[shadow]
books = ["RULES_ONLY", "NO_INSIDER", "NO_CROWDING_VETO"]   # PAPER book is implicit FULL

[llm]
provider = "openrouter"          # or "openai"; one OpenAI-compatible client
model = "anthropic/claude-sonnet-4"
base_url = ""
timeout_s = 30

[education]
level = "beginner"
concept_repeat_limit = 3
```

Parameter budget unchanged: **max 3 tunable parameters**, walk-forward only.

---

## 3. Data layer — full subsystem design

### 3.1 Topology: four zones, strictly one-directional flow

```
  SOURCES                RAW VAULT             CANONICAL STORE            DERIVED STATE
┌──────────┐   fetch   ┌─────────────┐ parse ┌──────────────────┐ derive ┌──────────────────┐
│ EODHD    │──────────▶│ append-only │──────▶│ bars/      parquet│──────▶│ indicator_state  │
│ Alpaca   │  httpx +  │ zstd blobs  │ pydan-│  (DuckDB queries) │ numpy │ month_end_closes │
│ SEC      │  tenacity │ + manifest  │ tic   │ state/     DuckDB │ O(1)  │ regime_state     │
│ OpenIns. │  + rate   │ (content-   │ models│  (per-conn.  tx)  │ incr. │ mention_baseline │
│ Reddit   │  limiter  │  addressed) │       │                   │       │ (DuckDB)         │
└──────────┘           └─────────────┘       └──────────────────┘       └────────┬─────────┘
                                                                                  │
                                                              ACCESS: ports (MarketData,
                                                              Fundamentals, …) backed by
                                                              DuckDB views — domain code
                                                              sees ports only
```

Properties: re-parseable forever (vault keeps every raw byte), reproducible (everything downstream is a deterministic function of the vault), and swappable (fixture adapters plug in at the ACCESS layer for replay/CI).

### 3.2 Zone 1 — Connectors

One base class, five implementations. Shared machinery: `httpx` client, `tenacity` retry (exponential backoff + jitter, max 5), per-source token-bucket rate limiter, response → vault before any parsing, structured fetch log events.

| Source | Endpoint(s) | Auth / etiquette | Rate budget | Cadence |
|---|---|---|---|---|
| **EODHD** | `/eod/{sym}`, `/fundamentals/{sym}`, `/calendar/earnings` | API key | plan-dependent; batch EOD endpoint for daily Δ | daily 17:30 ET |
| **Alpaca Data** (informational only) | `alpaca-py` market-data: latest quotes/bars, trading calendar | key/secret | generous free tier (IEX feed) | decision time |
| **SEC** | `company_tickers.json` | **mandatory descriptive User-Agent** per SEC fair-access policy | ≤10 req/s (we use 1) | weekly |
| **OpenInsider** | screener HTML (latest cluster buys, by-date) | none — be polite: 1 req/3s, identify UA, cache aggressively | ~30 pages/day max | daily |
| **Reddit public** | `https://www.reddit.com/r/{sub}/new.json` style public endpoints | UA required; unauthenticated ≈10 req/min | counts only, 2 subs | daily |

Failure policy: a source failing **degrades, never blocks** — pipeline runs with `SOURCE_DEGRADED(source)` event; mechanisms depending on it fall back (M5 boost → 0, M6 veto → fail-open with raised entry bar, earnings calendar stale → blackout window widened by 1 day). Only *price* staleness sets `DATA_HALT`.

### 3.3 Zone 2 — Raw vault

Append-only directory tree of zstd-compressed raw payloads:

```
vault/{source}/{yyyy}/{mm}/{dd}/{fetch_id}.zst     + vault/manifest.db
```

`fetch_id = sha256(source|endpoint|params|ingest_ts)[:16]`; manifest rows record source, endpoint, params, ingest_ts, content hash, byte size. **Nothing is ever deleted or rewritten.** Cost is trivial (daily JSON/HTML for ~1k symbols compresses to a few MB/day). Payoff: any parser bug, schema change, or new mechanism can be replayed against history you already own — this is what makes the immutability contract real rather than aspirational.

### 3.4 Zone 3 — Canonical store (DuckDB for both access patterns)

Per ADR-0021 (supersedes ADR-0007), Alpha-Quant uses **DuckDB for both analytical and transactional access** — no SQLAlchemy Core or separate SQLite.

**Analytical data → Parquet, queried by DuckDB.** Daily bars, fundamentals snapshots, insider transactions, mention counts, corporate actions: columnar, scan-heavy, append-mostly.

```
canonical/bars/date=YYYY-MM-DD/part.parquet        # date-partitioned (one small file/day)
canonical/fundamentals/snapshot_date=.../
canonical/insider_tx/filed_date=.../
canonical/mentions/date=.../
canonical/corp_actions/effective_date=.../
```

Date partitioning makes as-of-date queries natural. DuckDB reads parquet globs directly with zero server footprint — and you already know this stack cold from the postgres-connector pipeline (PostgreSQL→DuckDB→Parquet); same pattern, new domain. (The 50-day tail prune was removed in P2.RO — storage cost was negligible and the prune created a real risk of insufficient history for indicator backfill after corporate actions.)

**Transactional state → DuckDB (direct).** Decisions, orders, fills, positions, equity curves, events, concept_log, indicator_state, catalog. Single-writer, ACID via DuckDB's per-connection transactions.

While splitting analytical and transactional stores is generally prudent, DuckDB is safe for both because:
- The pipeline is single-writer (no concurrent write access)
- DuckDB provides snapshot isolation per connection
- DuckDB state tables handle ACID row-level operations
- The `Store` port abstracts storage — migrating to PostgreSQL later requires only a new adapter (per ADR-0021)

Migration path: local Parquet → MinIO/S3 is behind DuckDB's path config; state → PostgreSQL requires a new `Store` adapter. Both are non-events.

### 3.5 Zone 4 — Derived state (the incremental engine)

Per-symbol `indicator_state` row: `{ema20, ema50, ema200, rsi_avg_gain, rsi_avg_loss, atr, last_close, last_date, updated_ts, status}` — all O(1) Wilder/EMA recurrences in plain numpy; no pandas-ta dependency needed because nothing recomputes windows. Plus `month_end_closes` (12 floats/symbol/year) for 12-1 momentum, regime state, and 30-day Reddit mention baselines.

This is what reconciles full raw history with 200-day indicators: EMAs update from one stored value; long raw history is unnecessary. Cold start: one-time 250-day backfill per symbol seeds the state (bootstrap does this). Integrity check in CI: recompute from full fixture history, compare to incrementally-built state to 1e-6.

**Corporate-action adjustment policy:** The system stores raw (unadjusted) `close` prices. `adj_close` from EODHD is retained in the `bars` schema but not consumed by the indicator engine — the indicator engine uses `close` (point-in-time raw prices). When a corporate action (split, dividend) occurs, the affected symbol's `indicator_state.status` is set to `STALE`, triggering a full backfill from raw bars on the next pipeline run. This is safer than applying adjustment factors to incremental state, since a split's ~50% price jump would corrupt recursive EMA/RSI/ATR despite any adjustment formula. The `adjust_price()` pure function in `domain/corp_actions.py` computes cumulative backwards adjustment factors for backtesting — it multiplies split ratios to produce a factor that makes historical prices comparable to current prices. Dividends are recorded but do not adjust prices (cash dividends don't change the price series structure).

### 3.6 Validation gates (between every zone)

`validate.py` runs declarative checks: calendar-gap detection, zero/negative price, |return| > 40% without a corporate-action record → symbol quarantined, fundamentals snapshot schema drift → parse quarantined (vault keeps the bytes), staleness → `DATA_HALT`. Implemented as plain predicate functions emitting `DataQuarantined`/`StalenessHaltSet` events — no rules-engine framework; ~15 checks don't justify one.

### 3.7 Bootstrap — 50 configurable symbols

`alpha-quant bootstrap` reads `[bootstrap]` config: fetches `history_years` of daily bars, fundamentals snapshots, earnings dates, OpenInsider history for the 50 listed symbols + SPY + VIX proxy; writes vault → canonical → seeds indicator_state; then freezes a **fixture bundle** (parquet + manifest.json with content hashes, pinned as `fixture_version`).

The default 50 are curated for behavioral coverage, not preference: steady large-cap trenders, high-beta names, at least one meme-prone ticker, an earnings-gap case, a recent split, a delisting/rename (exercises SEC-map hygiene). *(Synthetic overlays for missing-bar, stale-feed, and z>3 mention spike scenarios deferred — see P3+ backlog.)* Swap the list in config at will; re-bootstrap regenerates everything deterministically.

Development speeds: domain unit tests (ms) → full-DAG replay over fixtures (seconds–minutes for 3 simulated years) → real daily runs (only for connector/feed reality).

### 3.8 Library decisions (data layer + system)

| Concern | Choice | Why |
|---|---|---|
| HTTP | **httpx** | sync+async, HTTP/2, timeouts as first-class config |
| Retry/backoff | **tenacity** | declarative, per-connector policies |
| Rate limiting | small token-bucket util (~30 lines) | not worth a dependency |
| HTML parsing (OpenInsider) | **selectolax** | fast, lenient |
| Validation/models | **pydantic v2** | parse-don't-validate at zone boundaries |
| DataFrames | — (use DuckDB SQL + pyarrow) | polars removed from dependencies (was evaluated but unused) |
| Analytical SQL | **DuckDB** | zero-ops parquet queries; covers both analytical and transactional access |
| Columnar files | **pyarrow** (parquet, zstd codec) | standard |
| Compression | **zstandard** | vault blobs |
| Transactional DB | **DuckDB** (direct, via `app/store/state.py`) | ACID, single-writer, no ORM; supersedes SQLite/SQLAlchemy (ADR-0021) |
| Indicators | **numpy** recurrences (own ~100 lines) | incremental O(1); window libs unnecessary |
| Scheduling | **APScheduler** (cron fallback) | in-process, simple |
| Config | **pydantic-settings** + TOML | typed, env-overridable |
| Logging | **structlog** (JSON lines) | events + logs share shape |
| Testing | **pytest** | golden replay, integration tests, unit tests |
| LLM client | **httpx** against OpenAI-compatible API | one adapter: OpenAI + OpenRouter |
| Market data SDK | **alpaca-py** (data module only) | no trading module imported outside broker adapter — enforced by lint rule |
| Dashboard | **Streamlit** | reads DuckDB state store via Store port, zero coupling |

---

## 4. Clock virtualization and replay

The `Clock` port is wired for most app-layer consumers (pipeline, store, paper, alerts, halt, fixtures, vault) and key domain functions. `SystemClock` (live) or `VirtualClock` (replay/backtest) injects time. A small number of remaining direct clock reads (`datetime.now(UTC)` in Pydantic event defaults, vault, pipeline, and some adapters) are tracked as known issues. `alpha-quant replay --from-date 2023-01-01 --to-date 2025-12-31` drives the **entire DAG** against fixture adapters — ingest, validation, halts, decisions, paper fills, events, journals, reports — in minutes. CI runs a **golden replay** (January 2024 fixture month; decision log + paper equity curve must hash-match the committed golden output; intended changes re-bless the golden file in the same PR). The single highest-leverage testing investment in the project.

---

## 5. Decision engine — 8 mechanisms

(Unchanged from v1.1; summary.) **M1** universe (S&P500+MidCap400, $5+, $5M ADV, SEC-map validated) · **M2** regime gate (SPY EMA50/200, breadth, VIX → RISK_ON/CAUTION/RISK_OFF) · **M3** technical score (trend, Gaussian RSI 52±22, MACD histogram, 12-1 momentum, volume confirmation, ATR% sanity) · **M4** fundamental quality gate, binary (positive OCF, sector-relative D/E, no recent negative surprise, accruals sane) · **M5** insider cluster signal (≥2 officers/directors, ≥$200k net, 30d → boost; Cohen/Malloy/Pomorski 2012) · **M6** crowding veto (Reddit mention z>3 → 14-calendar-day entry block ≈ 10 trading days; count arithmetic, never LLM sentiment) · **M7** earnings blackout (no entries ≤3 days before earnings) · **M8** composite ranking (0.6·technical + 0.25·momentum + 0.15·insider; gates first; liquidity tiebreak). Degradation per §3.2 when a source is down. Rejected: ML, LLM scoring, pairs, analyst revisions.

---

## 6. Position sizing

`shares = (equity × 1%) / (2 × ATR)`; caps ≤15%/position, gross ≤80%, ≤2/sector; × regime multiplier × drawdown-ladder multiplier. Pure O(1) functions.

---

## 7. Risk management — hard rules, structurally exit-only

Unchanged in substance: 2×ATR initial stop; trail after +1R; 50% partial at +2R; 30-day time stop; drawdown ladder (−10% → gross ×0.5, −15% → flat + manual restart); −3% daily loss halt; staleness halt; kill switch (`halt` → lockfile blocks scheduler). `risk.py` can only reduce/close. **Stop execution semantics now live in the fill model (§9.2)** since there is no broker to hold stop orders.

---

## 8. Shadow ablation books

The paper book (§9) is the FULL system. Alongside it, shadow books — RULES_ONLY (permanent internal baseline), NO_INSIDER, NO_CROWDING_VETO — consume the same live data and domain code with mechanisms toggled, filled by the same fill model, plus an SPY buy-and-hold curve. **Live ablation, walk-forward by construction:** a mechanism lagging its ablation twin for two consecutive quarters gets feature-flagged off. Books update on every run, including halted ones — strategy evaluation never stops.

---

## 9. Internal paper-trading engine *(replaces broker execution)*

### 9.1 The paper book is the portfolio

There is no external broker. `app/paper.py` maintains the authoritative portfolio in DuckDB (via the Store port): cash, positions, orders, fills, equity curve — all written transactionally with their Decision lineage. Alpaca contributes *information only* (latest quotes for marking and fill realism; trading calendar); the `alpaca-py` trading module is only imported by the broker adapter (`alpaca_broker.py`) which is inactive in v1.

What this removes: broker reconciliation, order-rejection handling, partial-fill plumbing, API-key risk on the execution path. What it forfeits (stated honestly, also to the user via a concept card): real fill competition, real spreads at size, exchange halts, borrow/locate realities. Paper results are therefore an **upper bound** on live performance — the monthly report says so explicitly.

### 9.2 Fill model semantics (`domain/fills.py` — used by backtest, replay, paper, shadows)

Daily-bar discipline; decisions at close of day *T*, executions at *T+1*:

- **Entries:** filled at *T+1 open* + slippage (5 bps + half-spread estimate from the latest Alpaca quote when live, fixed estimate in replay/backtest). If *T+1* open gaps beyond the limit band (±2% of decision-time quote), the order cancels and re-evaluates next run — identical to the old broker behavior.
- **Stops:** evaluated against *T+1* intraday range: if `low ≤ stop`, exit at `min(open, stop)` − slippage. Gap-downs fill at the open, not the stop — the pessimistic, honest treatment; ATR stops that "never lose more than 1%" on paper but gap through in reality are how paper systems lie. Ours doesn't.
- **Partial takes / trails:** trail levels recomputed from *T* close; same `low/high` touch logic, conservative side always.
- **Dividends & splits:** cash dividends credited on pay date (EODHD calendar); splits adjust positions and stops atomically with the corporate-action record.
- **Determinism:** `fill_id = hash(decision_id, fill_date)`; re-running a day is idempotent (I7 still holds).

### 9.3 Self-consistency (replaces broker reconciliation)

Nightly assertion set over the portfolio state: `cash + Σ(position marks) == equity_curve point`; every position traces to fills; every fill to an order; every order to a Decision; no orphans. A violation is a **software bug, full halt** — stricter than broker reconciliation ever was, because there is no counterparty to blame.

### 9.4 Path to live (explicitly out of v1)

The `broker.py` port (`submit/cancel/positions/account`) is specified now and implemented never-until-needed. Going live later = writing one adapter + re-adding a reconciliation stage; domain, risk, and pipeline are untouched. The §14 "live gate" criteria are retained for that future decision.

---

## 10. Event log

Append-only typed events from every stage: `PipelineRunStarted/Completed · DataIngested · DataQuarantined · SourceDegraded · StalenessHaltSet · IndicatorStateUpdated · RegimeChanged · CandidateScored · CandidateBlocked(reason) · CandidatePromoted · OrderSimulated · FillBooked · StopAdjusted · PartialTaken · TimeStopTriggered · DrawdownLadderTripped · BookMarked · ConsistencyViolation`. Narrator, reports, and dashboard consume events only — never pipeline internals. Audit trail and debugging time-machine in one (your `ScorecardRefreshed` pattern, generalized).

---

## 11. Narration & education layer

Unchanged from v1.1, three principles: **(1)** every number is injected from lineage/events — the LLM polishes prose and pedagogy around rendered facts, a post-render checker verifies every figure exists in source data, mismatch → plain template, LLM outage degrades style never correctness; **(2)** two-layer output — plain-English narration + expandable concept cards from a hand-written registry (~20 cards: ATR, stop-loss, regime, sizing, drawdown, slippage, *paper-vs-live gap*, …); **(3)** progressive disclosure via `concept_log` (`concept_repeat_limit` full showings, then one-liners). `alpha-quant ask "why didn't you buy TSLA?"` answers from recorded `CandidateBlocked` events — the LLM presents recorded reasoning, never generates new reasoning. Negative-space narration ("no trades today, regime is CAUTION...") included by design.

---

## 12. Reporting

Event-log consumers, Markdown + dashboard HTML, optionally emailed. **Daily journal:** regime, data health, actions and non-actions with reasons, distance-to-stop risk map, one new concept card. **Weekly review:** rebalance rationale, candidate funnel with block reasons, book deltas, upcoming blackouts, plain-language market recap. **Monthly report:** paper book vs SPY vs all shadow books (the live ablation scoreboard), attribution by mechanism, risk stats, turnover/cost drag, config-change log, paper-vs-live caveat, learning recap from concept_log.

---

## 13. Daily run sequence

```
17:30 ET, APScheduler (VirtualClock in replay):
 1. ingest      EODHD Δ, fundamentals snapshot, earnings cal,
                OpenInsider Δ, Reddit counts, SEC map (weekly)     [events]
 2. validate    gaps/staleness/splits → DATA_HALT?                 [events]
 3. derive      incremental indicator_state, month-ends            [events]
 4. regime      M2                                                 [events]
 5. risk        stops/trails/time-stops/ladder → exit instructions [events]
 6. decide      gates M1,M4,M6,M7 → scores M3,M5 → M8 targets      [events]
 7. simulate    queue T+1 orders for paper book + shadow books     [events]
 8. persist     decisions, lineage
 9. narrate     daily journal (LLM-polished, fact-checked)
─────────────────────────────────────────────────────────────────
 next open:     fill queued orders via fills.py against T+1 bars,
                book fills, mark equity, run self-consistency (§9.3)
```

Weekly rebalance = step 6 considers replacements; daily runs manage risk and fill vacated slots.

---

## 14. Backtesting and evaluation

No vectorbt for portfolio simulation (path-dependent constraints); event-driven daily loop over `domain/fills.py` — a decade in seconds at this scale; vectorbt for single-signal research only. **One fill model across backtest/replay/paper/shadows ⇒ comparable by construction.** Costs: 5 bps + half-spread on every fill. Walk-forward only (3y/1y), ≤3 core research parameters (threshold score, RSI center, Kelly fraction). Many system-level config knobs exist (stop ATR multiples, trailing thresholds, drawdown ladder, sector limits) but are fixed per walk-forward window. Baselines always: SPY + RULES_ONLY; every mechanism beats its ablation or is flagged off. Metrics: CAGR, max DD, Sharpe, Sortino, exposure-adjusted return, turnover, win rate, payoff. Live-gate criteria retained for the future broker decision (§9.4).

---

## 15. Implementation phases

**Phase 0 — Skeleton + fixtures (wk 1).** Repo, ports, config, Clock, event log, fake adapters, `bootstrap` (50-symbol config), fixture bundle frozen, golden-replay harness in CI. *AC: full DAG end-to-end on fixtures with stub mechanisms.*

**Phase 1 — Data layer (wk 1–3).** Connectors + vault + canonical (parquet/DuckDB) + derive + validate, per §3. *AC: double ingest ⇒ zero new canonical rows; vault replay of one fixture day reproduces canonical bit-identically; indicator_state matches full-history recompute to 1e-6 for 20 symbols; fake-vs-real adapter contract tests pass.*

**Phase 2 — Domain + backtester + paper engine (wk 3–5).** M1–M4, M7, M8, sizing, risk, fills; backtester; paper book + RULES_ONLY shadow on fixtures; self-consistency checks. *AC: 10-year backtest <60s; hand-computed 5-trade fixture matches fills exactly, including a gap-through-stop case; property tests on cap invariants; golden replay green.*

**Phase 3 — Alt-data signals (wk 5–6).** OpenInsider + Reddit connectors, M5, M6, ablation books. *AC: each mechanism non-negative walk-forward Sharpe impact or flagged off; fixture meme-spike triggers M6; source-degradation fallbacks fire correctly.*

**Phase 4 — Narration + education + reports (wk 6–7).** Narrator, ~20 concept cards, consistency checker, `ask`, daily/weekly/monthly reports, Streamlit dashboard over events. *AC: every narrated number traceable (automated); LLM outage ⇒ template journal, zero pipeline impact; replayed fixture history yields a readable 6-month journal.* *(Before live data on purpose: the journal is your primary debugging instrument.)*

**Phase 5 — Live data operation (wk 7–8).** Real connectors on schedule, alerting, `status`/`halt` ops, backup routine (DuckDB + vault sync). *AC: chaos test — kill mid-run, restart, idempotent; forced staleness ⇒ halt + alert; 2 weeks unattended runs clean.*

**Phase 6 — Evaluation period (≥3 months).** Paper + shadow books daily. Outcome: keep/kill mechanisms per ablation; only *then* revisit the live-broker question (§9.4).

---

## 16. System invariants (assertion-enforced)

I1. No order without a persisted Decision row.
I2. `risk.py` outputs only reduce or close exposure.
I3. LLM output never crosses into the decision path.
I4. Vault is append-only; closed bars, filed insider records, and fixture bundles are immutable.
I5. Per-position risk-at-stop ≤ 2% equity at order time.
I6. Gross exposure ≤ cap after every fill batch.
I7. Identical inputs + config + git sha ⇒ identical decisions and fills (golden replay in CI).
I8. Backtest, replay, paper, and shadows execute the same domain functions and the same fill model.
I9. Domain functions do not read the OS clock; app-layer modules should use the Clock port (the `events.py` model default is the only domain exception; remaining app-layer clock reads are tracked issues).
I10. Every number in user-facing text exists in the lineage/event data it cites.
I11. All books update on every run, including halted ones.
I12. The paper book passes self-consistency (§9.3) after every fill batch; violation ⇒ full halt.
I13. `alpaca-py` trading module is only imported in the broker adapter (`alpaca_broker.py`); Alpaca is data-only outside the inactive broker path.

## 17. Retained red flags

No LLM stock-picking/sizing; no agent swarms; no intraday data; no derivatives; no custom risk models; ≤3 core research parameters (walk-forward optimized: threshold, RSI center, Kelly fraction); system-level knobs fixed per window; no signal that loses to its ablation; no narration that invents numbers; no optimistic stop fills — gaps fill at the open.

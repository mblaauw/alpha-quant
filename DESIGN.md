# Alpha-Quant — Implementation-Ready Design (v1.2)

Deterministic, daily-cadence, long-only equity system with an **internal paper-trading engine** — no broker dependency. All market, fundamental, insider, and sentiment data is sourced through **Alpha-Lake**, a separate data-plane system accessed via the `LakeGateway` port. LLM is explainer/educator only — never in the decision path. Ports-and-adapters architecture: pure domain core; adapters for data, LLM, storage; virtualized clock; fixture/replay harness; shadow ablation books; append-only event log; narration/education layer.

**v1.2 changes (historical):** Alpaca demoted to data-only (old §3); execution is now a fully internal paper engine (§9) — reconciliation removed, stop semantics defined against daily bars; bootstrap universe = 50 configurable symbols (§3.7); the data layer was a fully designed subsystem with tool and library decisions (old §3, superseded by v1.3); phases and invariants revised.

**v1.3 (Alpha-Lake data-plane extraction):** All data ingestion (connectors, vault, canonical Parquet source-data store, `fetch_id` lineage) is removed from Alpha-Quant and delegated to Alpha-Lake. The `LakeGateway` port provides PIT reads; `InProcessLakeGateway` imports the `alpha_lake` library in-process; `FixtureLakeGateway` provides deterministic fixture replay. The pipeline no longer ingests data — it reads from the lake.

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
│   ├── events.py                # 22 discriminated domain event types (plus BaseDomainEvent base)
│   ├── normalize.py             # boundary parsing: bytes → pydantic models
│   ├── _normalize_helpers.py    # normalization utility functions
│   ├── validate.py              # quality gates → QUARANTINE/DATA_HALT
│   ├── derive.py                # incremental O(1) indicator engine (numpy)
│   ├── universe.py              # M1 universe selection
│   ├── regime.py                # M2 regime detection
│   ├── technical.py             # M3 technical score
│   ├── fundamental.py           # M4 fundamental quality gate
│   ├── insider_signal.py        # M5 insider cluster signal
│   ├── crowding.py              # M6 crowding veto
│   ├── blackout.py              # M7 earnings blackout
│   ├── ranking.py               # M8 composite ranking
│   ├── scoring.py               # composite score computation
│   ├── ablation.py              # shadow ablation books
│   ├── fills.py                 # fill model (across backtest/replay/paper)
│   ├── risk.py                  # risk management (stops, trails, drawdown)
│   ├── sizing.py                # position sizing
│   ├── loop_helpers.py          # shared decision-loop helpers
│   ├── invariants.py            # self-consistency assertions
│   ├── events.py                # domain event types
│   ├── narration.py             # narration context builder
│   ├── journal.py               # daily journal generator
│   ├── reporting.py             # weekly/monthly report generators
│   ├── fact_check.py            # LLM fact-checking
│   ├── ask.py                   # natural-language query
│   ├── calendar.py              # trading calendar utilities
│   ├── corp_actions.py          # corporate action adjustment factors
│   ├── degradation.py           # lake-health-based degradation fallback
│   ├── constants.py             # shared constants
│   └── exceptions.py            # AlphaQuantError, DataNormalizationError
├── ports/                       # ABC interfaces for all external dependencies
│   ├── __init__.py              # re-exports
│   ├── broker.py                # port interface; FakeBroker and AlpacaBroker adapters exist, live execution out of v1 scope (§9.4)
│   ├── clock.py                 # injected clock abstraction
│   ├── event_sink.py            # typed event persistence
│   ├── fundamentals.py          # fundamentals snapshot access (backed by LakeGateway)
│   ├── insider_feed.py          # insider transaction access (backed by LakeGateway)
│   ├── lake.py                  # LakeGateway — PIT data access to Alpha-Lake
│   ├── llm.py                   # LLM interface (explainer only — never in decision path)
│   ├── market_data.py           # bar/quote data access (backed by LakeGateway)
│   ├── sentiment_feed.py        # mention count access (backed by LakeGateway)
│   └── store.py                 # DuckDB-backed state store
├── adapters/
│   ├── real/                    # production implementations
│   │   ├── __init__.py          # re-exports
│   │   ├── alpaca_broker.py     # broker adapter (inactive in v1)
│   │   ├── clock.py             # SystemClock — wraps datetime.now(UTC)
│   │   ├── event_sink.py        # DuckDB + SQLite event sinks
│   │   ├── lake_data.py         # LakeMarketData, LakeFundamentals, LakeInsiderFeed, LakeSentimentFeed — port wrappers over LakeGateway
│   │   ├── lake_inprocess.py    # InProcessLakeGateway — imports alpha_lake library in-process
│   │   └── llm_adapter.py       # OpenAI-compatible LLM client
│   └── fake/                    # test/fixture implementations
│       ├── __init__.py          # re-exports
│       ├── canned_llm.py        # static template responses
│       ├── fake_broker.py       # in-memory broker
│       ├── fake_event_sink.py   # in-memory event store
│       ├── fixture_store.py     # in-memory store for test isolation
│       ├── lake_fixture.py      # FixtureLakeGateway — lake-shaped fixture reader with PIT visibility
│       └── virtual_clock.py     # deterministic clock for replay/backtest
├── app/                         # application wiring + infrastructure
│   ├── __init__.py              # empty (re-exports handled at subpackage level)
│   ├── _loop.py                 # shared decision-loop helpers
│   ├── alerts.py                # alert generation
│   ├── backtest.py              # historical backtest engine
│   ├── backup.py                # backup utilities (DuckDB state store)
│   ├── bootstrap.py             # fixture generation (deterministic)
│   ├── catalog.py               # fixture integrity verification
│   ├── config.py                # pydantic-settings + TOML loading
│   ├── dashboard.py             # Streamlit dashboard
│   ├── event_log.py             # typed event log
│   ├── factory.py               # dependency injection factory
│   ├── fixtures.py              # freeze_bundle: parquet + manifest writer
│   ├── halt.py                  # halt file management
│   ├── paper.py                 # paper trading engine
│   ├── pipeline.py              # main daily pipeline (reads from lake, no ingest)
│   ├── pipeline_steps.py        # pipeline step models
│   ├── replay.py                # golden replay harness
│   ├── scheduler.py             # APScheduler-based daily scheduling
│   ├── step_models.py           # pipeline step data models
│   └── store/                   # DuckDB-backed state store (decisions, orders, positions, indicators)
│       ├── __init__.py          # re-exports
│       ├── admin_store.py       # run metadata, config snapshots
│       ├── decision_store.py    # decision records
│       ├── event_store.py       # event log access
│       ├── indicator_store.py   # indicator state access
│       ├── journal_store.py     # journal entries
│       ├── order_store.py       # order persistence
│       ├── position_store.py    # position persistence
│       └── state.py             # CanonicalStore composite (inherits all mixins)
├── tests/                       # test suite (repo root — not under src/)
│   ├── unit/                    # unit tests (pure domain functions)
│   ├── integration/             # integration tests (adapter contracts)
│   ├── chaos/                   # chaos tests (kill-mid-run, corruption)
│   └── qa/                      # QA smoke tests (shell scripts)
├── fixtures/                    # versioned bootstrap dataset (§3.7) — repo root
│   └── golden/                  # golden replay outputs for CI
├── docs/                        # documentation — repo root
│   ├── adr/                     # architecture decision records
│   ├── architecture/            # C4 diagrams (LikeC4 DSL)
│   ├── planning/                # backlog, roadmap, issue creation
│   └── spike-*.md               # evaluation spike reports
├── src/app/concepts/            # concept cards (markdown)
├── scripts/                     # utility scripts
├── config.toml                  # config template (secrets in config.local.toml)
└── config.local.toml.example    # local override template
```

**Rationale for domain/ layout:** `normalize.py`, `validate.py`, and `derive.py` live in `domain/` because they are pure functions with no I/O — they take data and return data. Normalization is boundary parsing (HTTP response bytes → pydantic models), but the parsing itself has no adapter dependency. This keeps the domain core complete (all data transformations are together) while ports and adapters remain separate in their own layers.

**Rules:** `domain/` imports nothing from `adapters/`. Every connector has a fixture-backed fake twin on the same port. The pipeline never knows which reality it runs in.

---

## 2. Configuration

```toml
[bootstrap]
symbols = ["AAPL","MSFT","NVDA", "...4 more"]   # 7 trading + SPY + ^VIX, fully configurable
history_years = 3
include_benchmarks = ["SPY", "^VIX"]

[data]
indicator_state = true
staleness_halt_hours = 30
fixture_version = "v1"

[lake]
mode = "in_process"                   # "fixture" | "in_process" | "rest" (deferred)
config_path = "../alpha-lake/config/stack.toml"
snapshot_id = ""
price_mode = "split_adjusted"
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

# No provider API keys for data collection — all market data is read
# through Alpha-Lake via the LakeGateway port. Alpaca API keys remain
# for the broker adapter if live execution is enabled in future.
```

Parameter budget unchanged: **max 3 tunable parameters**, walk-forward only.

---

## 3. Data Plane: Alpha-Lake

### 3.1 Topology — lake as single data source

All market, fundamental, insider, and sentiment data is read from **Alpha-Lake**, a separate data-plane system that handles ingestion, storage, and point-in-time (PIT) serving. Alpha-Quant has no connectors, no vault, and no canonical source-data store — it is a pure consumer of lake data.

```
                       ALPHA-QUANT PIPELINE
                    ┌──────────────────────────┐
                    │  LakeGateway (port)        │
                    │  ┌──────────────────────┐  │
  ALPHA-LAKE ◀──────┤  │ InProcessLakeGateway │  │
  (DuckDB catalog)  │  │ FixtureLakeGateway   │  │
                    │  └──────────────────────┘  │
                    │         │                   │
                    │         ▼                   │
                    │  ┌──────────────────────┐  │
                    │  │ LakeMarketData        │  │
                    │  │ LakeFundamentals      │  │  ← port wrappers
                    │  │ LakeInsiderFeed       │  │
                    │  │ LakeSentimentFeed     │  │
                    │  └──────────────────────┘  │
                    │         │                   │
                    │         ▼                   │
                    │  ┌──────────────────────┐  │
                    │  │ domain: derive,       │  │
                    │  │ score, rank, size,    │  │
                    │  │ fill, risk, journal   │  │
                    │  └──────────────────────┘  │
                    └──────────────────────────┘
```

Every read is a PIT query driven by the clock's `as_of` timestamp. The pipeline never ingests raw data — it asks the lake "what did we know as of time T?" for bars, fundamentals, insider transactions, earnings dates, and mention counts.

### 3.2 LakeGateway port (`ports/lake.py`)

```python
class LakeGateway(ABC):
    def bars(self, symbol, start, end, as_of, price_mode) -> list[Bar]: ...
    def latest_bar(self, symbol, as_of) -> Bar | None: ...
    def trading_calendar(self, start, end) -> list[TradingDay]: ...
    def fundamentals(self, symbol, as_of) -> FundamentalsSnapshot | None: ...
    def earnings_calendar(self, start, end, as_of) -> list[EarningsEntry]: ...
    def insider_transactions(self, symbol, as_of) -> list[InsiderTransaction]: ...
    def mention_counts(self, symbol, days, as_of) -> list[MentionCount]: ...
    def dataset_health(self) -> dict[str, object]: ...
    def pin_snapshot(self, snapshot_id) -> None: ...
```

The `as_of` parameter is mandatory on every data read — this is what makes replay deterministic. `dataset_health()` returns per-dataset staleness/availability, used by `domain/degradation.py` to compute fallback multipliers and trigger `DATA_HALT` on price staleness.

### 3.3 Adapters

| Adapter | File | Mode | Description |
|---|---|---|---|
| **InProcessLakeGateway** | `adapters/real/lake_inprocess.py` | `in_process` | Imports `alpha_lake` library in-process; connects to DuckDB catalog; resolves symbols via security master; serves PIT panels. Live mode. |
| **FixtureLakeGateway** | `adapters/fake/lake_fixture.py` | `fixture` | Reads fixture Parquet files shaped like lake views; enforces PIT visibility via `available_at <= as_of`. Deterministic replay. |
| **RestLakeGateway** | *(deferred)* | `rest` | Raises `NotImplementedError` — to be implemented when Alpha-Lake deploys PIT-serving over REST. |

The `LakeMarketData`, `LakeFundamentals`, `LakeInsiderFeed`, and `LakeSentimentFeed` wrappers (`adapters/real/lake_data.py`) implement the individual domain port interfaces (`MarketData`, `Fundamentals`, `InsiderFeed`, `SentimentFeed`) by delegating to `LakeGateway` with `as_of=self._clock.now()`.

### 3.4 Failure policy — lake health based

Degradation is derived from `LakeGateway.dataset_health()` (`domain/degradation.py`):

```python
health = lake_gateway.dataset_health()
degradation = health_to_degradation(health)
halt = is_price_stale(health, staleness_hours=30)
```

- **Per-dataset staleness:** If `fundamentals`, `insider_tx`, or `attention_metrics` are empty or stale, the corresponding mechanism degrades (M5 boost → 0, M6 veto → fail-open with raised entry bar, M4 gate → pass-through).
- **Price staleness:** If the `bars` dataset's `latest_available_at` is more than 30 hours behind the clock, the pipeline sets `DATA_HALT` — no trading until fresh bars arrive.
- **Lake failure:** If the lake connection itself fails, the pipeline halts (the lake is the sole data source; there is no fallback connector).

### 3.5 Derived state (local incremental engine)

While lake storage uses the lake's catalog schema, Alpha-Quant maintains its own **incremental indicator state** in the local DuckDB store:

```
indicator_state (per symbol, O(1) recurrences):
  ema20, ema50, ema200, rsi_avg_gain, rsi_avg_loss, atr,
  last_close, last_date, updated_ts, status
```

Plus `month_end_closes` (12 floats/symbol/year) for 12-1 momentum, regime state, and 30-day mention baselines. All in plain numpy — no pandas-ta.

**Corporate-action adjustment:** The system reads adjusted prices from the lake (`price_mode="split_adjusted"`). The lake handles split/dividend adjustments in its serving layer. The local indicator engine consumes `adj_close` for incremental state. When a corporate action changes the price history, lake provides the adjusted series; the local indicator engine backfills from lake data if `status` is `STALE`.

### 3.6 Validation — between lake and local state

`validate.py` runs declarative checks on lake data: calendar-gap detection, zero/negative price, |return| > 40% without corporate-action record → symbol quarantined. Staleness → `DATA_HALT` (via `is_price_stale()`). Implemented as plain predicate functions emitting `DataQuarantined`/`StalenessHaltSet` events — ~15 checks, no rules-engine.

### 3.7 Bootstrap — fixture bundle from lake

`alpha-quant bootstrap` reads `[bootstrap]` config: connects to Alpha-Lake (or uses fixture data) to retrieve `history_years` of daily bars, fundamentals, earnings, insider, and mention data for the configured symbols; seeds local indicator state; then freezes a **fixture bundle** (Parquet + manifest.json with content hashes, pinned as `fixture_version`). The fixture bundle is shaped as lake views — compatible with `FixtureLakeGateway` for deterministic replay.

Development speeds: domain unit (ms) → full-DAG replay over fixtures (minutes for 3 simulated years) → live lake reads (production).

### 3.8 Library decisions (data layer + system)

| Concern | Choice | Why |
|---|---|---|
| HTTP | **httpx** | sync+async, HTTP/2, timeouts as first-class config |
| Validation/models | **pydantic v2** | parse-don't-validate at boundary |
| Analytical SQL | **DuckDB** | zero-ops queries on fixture Parquet; also backs local state |
| Columnar files | **pyarrow** (parquet, zstd codec) | standard; lake fixture bundles use this |
| Indicators | **numpy** recurrences (own ~100 lines) | incremental O(1); window libs unnecessary |
| Scheduling | **APScheduler** (cron fallback) | in-process, simple |
| Config | **pydantic-settings** + TOML | typed, env-overridable |
| Logging | **structlog** (JSON lines) | events + logs share shape |
| Testing | **pytest** | golden replay, integration tests, unit tests |
| LLM client | **httpx** against OpenAI-compatible API | one adapter: OpenAI + OpenRouter |
| Dashboard | **Streamlit** | reads DuckDB state store via Store port, zero coupling |

---

## 4. Clock virtualization and replay

The `Clock` port is wired for most app-layer consumers (pipeline, store, paper, alerts, halt, fixtures) and key domain functions. `SystemClock` (live) or `VirtualClock` (replay/backtest) injects time. A small number of remaining direct clock reads (`datetime.now(UTC)` in Pydantic event defaults, pipeline, and some adapters) are tracked as known issues. `alpha-quant replay --from-date 2023-01-01 --to-date 2025-12-31` drives the **entire DAG** against fixture adapters — lake reads, validation, halts, decisions, paper fills, events, journals, reports — in minutes. CI runs a **golden replay** (January 2024 fixture month; decision log + paper equity curve must hash-match the committed golden output; intended changes re-bless the golden file in the same PR). The single highest-leverage testing investment in the project.

---

## 5. Decision engine — 8 mechanisms

(Unchanged from v1.1; summary.) **M1** universe (S&P500+MidCap400, $5+, $5M ADV, SEC-map validated) · **M2** regime gate (SPY EMA50/200, breadth, VIX → RISK_ON/CAUTION/RISK_OFF) · **M3** technical score (trend, Gaussian RSI 52±22, MACD histogram, 12-1 momentum, volume confirmation, ATR% sanity) · **M4** fundamental quality gate, binary (positive OCF, sector-relative D/E, no recent negative surprise, accruals sane) · **M5** insider cluster signal (≥2 officers/directors, ≥$200k net, 30d → boost; Cohen/Malloy/Pomorski 2012) · **M6** crowding veto (mention z>3 → 14-calendar-day entry block ≈ 10 trading days; count arithmetic, never LLM sentiment) · **M7** earnings blackout (no entries ≤3 days before earnings) · **M8** composite ranking (0.6·technical + 0.25·momentum + 0.15·insider; gates first; liquidity tiebreak). Degradation per §3.4 when a lake dataset is stale. Rejected: ML, LLM scoring, pairs, analyst revisions.

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

There is no external broker. `app/paper.py` maintains the authoritative portfolio in DuckDB (via the Store port): cash, positions, orders, fills, equity curve — all written transactionally with their Decision lineage. Quote data for fill realism comes from the lake via `LakeMarketData.latest_quote()`. The `alpaca-py` trading module is only imported by the broker adapter (`alpaca_broker.py`) which is inactive in v1.

What this removes: broker reconciliation, order-rejection handling, partial-fill plumbing, API-key risk on the execution path. What it forfeits (stated honestly, also to the user via a concept card): real fill competition, real spreads at size, exchange halts, borrow/locate realities. Paper results are therefore an **upper bound** on live performance — the monthly report says so explicitly.

### 9.2 Fill model semantics (`domain/fills.py` — used by backtest, replay, paper, shadows)

Daily-bar discipline; decisions at close of day *T*, executions at *T+1*:

- **Entries:** filled at *T+1 open* + slippage (5 bps + half-spread estimate from the latest lake quote when live, fixed estimate in replay/backtest). If *T+1* open gaps beyond the limit band (±2% of decision-time quote), the order cancels and re-evaluates next run — identical to the old broker behavior.
- **Stops:** evaluated against *T+1* intraday range: if `low ≤ stop`, exit at `min(open, stop)` − slippage. Gap-downs fill at the open, not the stop — the pessimistic, honest treatment; ATR stops that "never lose more than 1%" on paper but gap through in reality are how paper systems lie. Ours doesn't.
- **Partial takes / trails:** trail levels recomputed from *T* close; same `low/high` touch logic, conservative side always.
- **Dividends & splits:** cash dividends credited on pay date (from lake earnings calendar); splits adjust positions and stops atomically with the corporate-action record.
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
 1. lake read   PIT: bars, fundamentals, insider, mentions,       [events]
                 earnings calendar, trading calendar (via gateway)
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

**Phase 1 — Data layer → Alpha-Lake integration (wk 1–3).** LakeGateway port, InProcessLakeGateway adapter, FixtureLakeGateway adapter, lake-shaped fixture bundles, derive + validate backed by lake reads. *AC: lake PIT read returns same data as fixture replay for same as_of; indicator_state matches full-history recompute to 1e-6 for 20 symbols; dataset_health drives correct degradation/halt.*

**Phase 2 — Domain + backtester + paper engine (wk 3–5).** M1–M4, M7, M8, sizing, risk, fills; backtester; paper book + RULES_ONLY shadow on fixtures; self-consistency checks. *AC: 10-year backtest <60s; hand-computed 5-trade fixture matches fills exactly, including a gap-through-stop case; property tests on cap invariants; golden replay green.*

**Phase 3 — Alt-data signals (wk 5–6).** Insider + mention feeds (via lake), M5, M6, ablation books. *AC: each mechanism non-negative walk-forward Sharpe impact or flagged off; fixture meme-spike triggers M6; dataset-health degradation fallbacks fire correctly.*

**Phase 4 — Narration + education + reports (wk 6–7).** Narrator, ~20 concept cards, consistency checker, `ask`, daily/weekly/monthly reports, Streamlit dashboard over events. *AC: every narrated number traceable (automated); LLM outage ⇒ template journal, zero pipeline impact; replayed fixture history yields a readable 6-month journal.* *(Before live data on purpose: the journal is your primary debugging instrument.)*

**Phase 5 — Live data operation (wk 7–8).** InProcessLakeGateway on schedule, alerting, `status`/`halt` ops, backup routine (DuckDB state store). *AC: chaos test — kill mid-run, restart, idempotent; forced staleness ⇒ halt + alert; 2 weeks unattended runs clean.*

**Phase 6 — Evaluation period (≥3 months).** Paper + shadow books daily. Outcome: keep/kill mechanisms per ablation; only *then* revisit the live-broker question (§9.4).

---

## 16. System invariants (assertion-enforced)

I1. No order without a persisted Decision row.
I2. `risk.py` outputs only reduce or close exposure.
I3. LLM output never crosses into the decision path.
I4. Fixture bundles are immutable once frozen; lake-sourced data is assumed immutable for the same `as_of`. (Data immutability is the lake's responsibility.)
I5. Per-position risk-at-stop ≤ 2% equity at order time.
I6. Gross exposure ≤ cap after every fill batch.
I7. Identical inputs + config + git sha ⇒ identical decisions and fills (golden replay in CI).
I8. Backtest, replay, paper, and shadows execute the same domain functions and the same fill model.
I9. Domain functions do not read the OS clock; app-layer modules should use the Clock port (the `events.py` model default is the only domain exception; remaining app-layer clock reads are tracked issues).
I10. Every number in user-facing text exists in the lineage/event data it cites.
I11. All books update on every run, including halted ones.
I12. The paper book passes self-consistency (§9.3) after every fill batch; violation ⇒ full halt.
I13. `alpaca-py` trading module is only imported in the broker adapter (`alpaca_broker.py`); Alpaca is broker-only and inactive in v1. All market data comes from Alpha-Lake, not from Alpaca.

## 17. Retained red flags

No LLM stock-picking/sizing; no agent swarms; no intraday data; no derivatives; no custom risk models; ≤3 core research parameters (walk-forward optimized: threshold, RSI center, Kelly fraction); system-level knobs fixed per window; no signal that loses to its ablation; no narration that invents numbers; no optimistic stop fills — gaps fill at the open.

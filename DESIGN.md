# Alpha-Quant — Architecture (v2.0)

> **⚠️ This document describes the v1 architecture.** \
> The codebase has been consolidated under `src/alpha_quant/` (Phase 5), the dashboard has been migrated from Streamlit to FastAPI + HTMX (Phase 6), DuckDB has been replaced by PostgreSQL as the operational system of record (Phase 4/P4.R/Phase 7), and the file-based halt has been replaced by database-backed halts (ADR-0040). See [REFERENCE_ARCHITECTURE.md](docs/architecture/REFERENCE_ARCHITECTURE.md) for the current architecture. This document will be rewritten for v2 in a future phase.

Deterministic, daily-cadence, long-only equity system with an internal paper-trading engine — no broker dependency, no data ingestion. All neutral market facts (bars, fundamentals, insider transactions, earnings, attention metrics) are sourced from **Alpha-Lake** via REST API. LLM is explainer/educator only — never in the decision path. Ports-and-adapters hexagonal architecture: pure domain core with typed ports; adapters for data, LLM, and storage; fixture replay; shadow ablation books; append-only event log.

---

## 1. Architecture overview

```
                          ┌──────────────────────────────────────────────────┐
                          │                  Alpha-Quant                    │
                          │  ┌────────────────────────────────────────────┐  │
                          │  │  app/cli.py (entry point)                   │  │
                          │  │    │                                        │  │
  ALPHA-LAKE ──REST───────┼──┤  app/factory.py create_alpha_lake_reader()   │  │
  (httpx)                 │  │    │                                        │  │
                          │  │    ▼                                        │  │
                          │  │  app/pipeline_v2.py  run_v2()               │  │
                          │  │    │                                        │  │
                          │  │    ▼                                        │  │
                          │  │  alpha_quant/ports/alpha_lake.py            │  │
                          │  │    │  AlphaLakeReadPort (Protocol)          │  │
                          │  │    ├── alpha_lake_rest.py (live)            │  │
                          │  │    └── alpha_lake_http_fixture.py (fixture)  │  │
                          │  │    │                                        │  │
                          │  │    ▼                                        │  │
                          │  │  Policy modules (real-time scored by AL):   │  │
                          │  │    technical_policy · fundamental_policy    │  │
                          │  │    insider_policy · attention_policy        │  │
                          │  │    earnings_blackout_policy · regime_policy │  │
                          │  │    composite_policy                         │  │
                          │  │    │                                        │  │
                          │  │    ▼                                        │  │
                          │  │  Domain (filled by pipeline):               │  │
                          │  │    fills · risk · sizing · ranking          │  │
                          │  │    invariants · events · narration          │  │
                          │  │    │                                        │  │
                          │  │    ▼                                        │  │
                          │  │  app/store/  CanonicalStore (DuckDB)        │  │
                          │  └────────────────────────────────────────────┘  │
                          └──────────────────────────────────────────────────┘
```

### Deployment

Single-machine: macOS/Linux workstation or headless server. 

- **CLI process** — `uv run alpha-quant run` triggers one daily pipeline run
- **Store** — DuckDB file in `data/` with tables for positions, orders, fills, decisions, events, portfolio snapshots
- **Config** — `config.toml` (secrets via `config.local.toml` or `ALPHA_QUANT_*` env vars)
- **Halt** — `data/.HALT` lockfile blocks pipeline runs

### Source directory layout

```
src/
├── app/                              # application wiring + pipeline
│   ├── cli.py                        # CLI entry point
│   ├── pipeline_v2.py                # run_v2() daily pipeline
│   ├── factory.py                    # DI: create_alpha_lake_reader, create_store, etc.
│   ├── config.py                     # pydantic-settings + TOML loading
│   ├── dashboard.py                  # Streamlit dashboard
│   ├── halt.py                       # halt file management
│   ├── backup.py                     # state store backup
│   └── store/                        # DuckDB-backed state store
│       ├── state.py                  # CanonicalStore composite
│       ├── position_store.py         # position persistence
│       ├── decision_store.py         # decision records
│       ├── order_store.py            # order persistence
│       ├── event_store.py            # event log access
│       ├── admin_store.py            # run metadata
│       ├── journal_store.py          # journal entries
│       └── fixture_store.py          # in-memory test store
├── alpha_quant/                      # domain-in-ports layer (Alpha-Lake contracts)
│   ├── contracts/alpha_lake.py       # dataclass contracts (BarObservation, DecisionPanel, ...)
│   ├── domain/
│   │   ├── decision_context.py       # extracted-facts facade over panel
│   │   └── policy/                   # 7 policy modules (evaluate on DecisionContext)
│   │       ├── __init__.py
│   │       ├── technical_policy.py
│   │       ├── fundamental_policy.py
│   │       ├── insider_policy.py
│   │       ├── attention_policy.py
│   │       ├── earnings_blackout_policy.py
│   │       ├── regime_policy.py
│   │       └── composite_policy.py
│   ├── ports/alpha_lake.py           # AlphaLakeReadPort (Protocol)
│   └── adapters/
│       ├── real/alpha_lake_rest.py   # AlphaLakeRestClient (httpx)
│       └── fake/alpha_lake_http_fixture.py  # AlphaLakeHttpFixtureClient
├── domain/                           # pure functions (no I/O)
│   ├── models.py                     # pydantic models (frozen)
│   ├── events.py                     # discriminated domain events
│   ├── fills.py                      # fill model
│   ├── risk.py                       # stops, trails, drawdown
│   ├── sizing.py                     # position sizing
│   ├── ranking.py                    # candidate ranking
│   ├── invariants.py                 # self-consistency assertions
│   ├── narration.py                  # narration context builder
│   ├── journal.py                    # daily journal
│   ├── reporting.py                  # weekly/monthly reports
│   ├── degradation.py                # lake-health fallback
│   ├── regime.py                     # Regime type
│   └── constants.py                  # shared constants
├── ports/                            # typed interfaces
│   ├── clock.py                      # Clock protocol
│   ├── store.py                      # Store protocol (positions, decisions, events, etc.)
│   ├── event_sink.py                 # event persistence
│   └── llm.py                        # LLM interface (explainer only)
├── adapters/                         # port implementations
│   ├── real/
│   │   ├── clock.py                  # SystemClock
│   │   ├── event_sink.py             # DuckDB event sink
│   │   └── llm_adapter.py            # OpenAI-compatible LLM
│   └── fake/
│       ├── fixture_store.py          # in-memory store (tests)
│       ├── canned_llm.py             # static LLM responses
│       ├── fake_event_sink.py        # in-memory event sink
│       └── virtual_clock.py          # deterministic clock
├── config.toml                       # config template
└── fixtures/v1/                      # JSON fixture files for replay
    ├── health.json
    ├── contract.json
    ├── universe.json
    └── decision-panel.json
```

**Rules:** `domain/` and `alpha_quant/domain/policy/` import nothing from `adapters/`. Every adapter has a fixture-backed fake twin on the same port.

---

## 2. Configuration

Sections: `[bootstrap]` (universe), `[data]` (fixture version), `[lake]` (REST/base_url), `[portfolio]`, `[paper]`, `[risk]`, `[llm]`, `[dashboard]`. Parameter budget: **max 3 tunable**, walk-forward only. See `config.toml` for defaults.

---

## 3. Data plane: Alpha-Lake

### 3.1 Sole data dependency

Alpha-Quant has exactly one data dependency: the **Alpha-Lake REST API** over authenticated HTTP (httpx). No local DuckDB catalogs, no Parquet files, no provider SDKs, no direct connector code.

### 3.2 AlphaLakeReadPort (`alpha_quant/ports/alpha_lake.py`)

```python
class AlphaLakeReadPort(Protocol):
    def health(self) -> AlphaLakeHealth: ...
    def read_contract(self, symbol: str) -> Contract | None: ...
    def read_universe(self) -> Universe: ...
    def read_decision_panel(self, symbols: list[str], as_of: datetime) -> DecisionPanel: ...
```

Single port, single method per data shape. `as_of` is mandatory on every read — this is what makes replay deterministic.

### 3.3 Adapters

| Adapter | File | Mode | Description |
|---|---|---|---|
| **AlphaLakeRestClient** | `adapters/real/alpha_lake_rest.py` | `live` / `rest` | httpx client against Alpha-Lake API |
| **AlphaLakeHttpFixtureClient** | `adapters/fake/alpha_lake_http_fixture.py` | `fixture` | Reads generated JSON fixture files; PIT-visibility via snapshot_id |

### 3.4 DecisionContext — extracted facts facade

Policy modules never receive raw panel data. `DecisionContext` wraps a `DecisionPanel` and exposes only computed facts:
- `bars` (BarObservation list)
- `latest_close()` / `latest_volume()`
- `indicator(name)` / `indicator_series(name)`
- `fundamental(metric_id)` / `fundamental_value(metric_id)` / `fundamental_tone(metric_id)`
- `insider_transactions`
- `earnings_events` / `has_future_earnings(as_of)`
- `attention_mentions`

### 3.5 Failure policy

- Lake health check failure → logged warning, pipeline continues (best-effort)
- Decision panel read failure → pipeline returns early with `halted=True`
- Individual symbol data missing → symbol skipped silently
- No SPY data → pipeline returns early (`no_spy_data`)

### 3.6 Fixture format

JSON files in `fixtures/v1/` (generated by `scripts/generate_fixtures.py` from legacy Parquet):
- `health.json` — `AlphaLakeHealth` (status, snapshots, latest_snapshot_id)
- `contract.json` — contract metadata per symbol
- `universe.json` — `Universe` with members list
- `decision-panel.json` — full panel with bars + indicators + fundamentals + insider + earnings + attention (3.4 MB, 9 symbols, 783 bars each)

---

## 4. Pipeline (`app/pipeline_v2.py`)

All modes (`live`, `rest`, `fixture`) go through a single pipeline function `run_v2()`.

### Daily run sequence

```
1. Decision panel  ── read panel from Alpha-Lake                         [events]
2. SPY regime      ── detect market regime (RISK_ON/CAUTION/RISK_OFF)    [events]
3. Risk            ── evaluate stops, trails, time stops, drawdown        [events]
4. Evaluate        ── for each candidate symbol:
                      · technical score  (M3)
                      · momentum score
                      · insider signal   (M5)
                      · fundamental gate (M4)
                      · attention gate   (M6)
                      · earnings blackout(M7)
                      · composite score  (M8)                            [events]
5. Rank & size     ── rank candidates × slots × regime × drawdown        [events]
6. Fill            ── entry orders at open + slippage (or gap-cancel)    [events]
7. Mark-to-market  ── update position prices
8. Consistency     ── check invariants
9. Persist         ── decisions, fills, events to DuckDB store
```

### Decision engine (policy modules)

| Mechanism | Module | Type | Description |
|---|---|---|---|
| M2 Regime | `regime_policy` | Gate | SPY trend + VIX → RISK_ON/CAUTION/RISK_OFF |
| M3 Technical | `technical_policy` | Score | Trend, RSI, MACD, momentum, volume, ATR |
| M4 Fundamental | `fundamental_policy` | Gate | Binary pass/fail: OCF, D/E, accruals, surprises |
| M5 Insider | `insider_policy` | Score | Cluster signal: ≥2 officers, ≥$200k, 30d |
| M6 Attention | `attention_policy` | Gate | Mention z-score veto on high crowding |
| M7 Blackout | `earnings_blackout_policy` | Gate | No entries ≤3 days before earnings |
| M8 Composite | `composite_policy` | Rank | Weighted composite (technical + momentum + insider) |

### Position sizing

`shares = (equity × risk_per_trade_pct) / (2 × ATR_dollar)` capped at `max_position_pct` per position, `max_positions` total, × regime multiplier × drawdown-ladder multiplier. Pure O(1) functions in `domain/sizing.py`.

### Risk management

2×ATR initial stop; trail after +1R; 50% partial at +2R; 30-day time stop; drawdown ladder (−10% → ×0.5, −15% → flat); −3% daily loss halt. `domain/risk.py` can only reduce or close exposure.

All risk checks run against daily bar range (low/close/high). Gap-through-stop fills at `min(open, stop)` — pessimistic always.

### Fill model (`domain/fills.py`)

Daily-bar discipline: decisions at close of day T, executions at T+1 open:
- **Entries:** T+1 open + slippage (5 bps). Gap > ±2% from decision → cancel.
- **Stops:** if T+1 low ≤ stop_price, fill at `min(open, stop_price)` − slippage.
- **Partials:** sell 50% at T+1 open − slippage.
- **Trails:** recomputed from T close, same low/high touch logic.

One fill model, every execution reality.

---

## 5. Event log

Append-only typed events from every stage:
`PipelineRunStarted · PipelineRunCompleted · PipelineStepCompleted · RegimeChanged · CandidateScored · CandidateBlocked · CandidatePromoted · FillBooked · StopAdjusted · PartialTaken · TimeStopTriggered · DrawdownLadderTripped · ConsistencyViolation · ErrorOccurred`

Narrator, reports, and dashboard consume events only — never pipeline internals.

---

## 6. Narration & education

LLM polishes prose and pedagogy around injected facts from events/lineage. Post-render checker verifies every figure exists in source data. No LLM-computed numbers in the decision path.

---

## 7. Shadow ablation books

PAPER book is the FULL system. Shadow books (RULES_ONLY, NO_INSIDER, NO_CROWDING_VETO) consume the same data with mechanisms toggled. Same fill model. SPY buy-and-hold baseline.

---

## 8. Self-consistency invariants

I1. No order without a persisted Decision row.
I2. `risk.py` outputs only reduce or close exposure.
I3. LLM output never crosses into the decision path.
I4. Identical inputs + config + git sha ⇒ identical decisions and fills.
I5. Per-position risk-at-stop ≤ cap at order time.
I6. Gross exposure ≤ cap after every fill batch.
I7. Domain functions do not read the OS clock.
I8. Every number in user-facing text exists in the lineage/event data.
I9. All books update on every run, including halted ones.
I10. `cash + Σ(market_value) ≈ equity` after every batch; violation ⇒ full halt.

---

## 9. Library choices

| Concern | Choice | Why |
|---|---|---|
| HTTP | **httpx** | sync+async, HTTP/2, timeouts |
| Models | **pydantic v2** | parse-don't-validate at boundary |
| State store | **DuckDB** | zero-ops, single-file |
| Config | **pydantic-settings** + TOML | typed, env-overridable |
| Logging | **structlog** | events + logs share shape |
| CLI | **typer** | typed CLI with rich output |
| Dashboard | **Streamlit** | reads DuckDB via Store port |
| Testing | **pytest** | unit + integration |
| LLM client | **httpx** | OpenAI-compatible |
| Testing types | **ty** | extremely fast Python type checker |

---

## 10. Non-goals (v2 scope)

Live brokerage execution, intraday trading, options/derivatives, shorting, ML models, multi-agent coordination, LLM-computed numbers anywhere. Paper results are an upper bound on live performance.

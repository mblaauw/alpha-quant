# Alpha-Quant Reference Architecture

## 1. Introduction

**Alpha-Quant** is a deterministic, daily-cadence, long-only equity trading system with an internal paper engine — no broker dependency. The LLM is explainer/educator only, never in the decision path. Built on a ports-and-adapters (hexagonal) architecture, the system enforces a pure domain core, with adapters for data, storage, LLM, a virtualized clock, fixture/replay harness, shadow ablation books, an append-only event log, and a narration/education layer.

The system operates across three execution realities — **backtest** (historical bars, research speed), **replay** (fixture data, full DAG, virtual clock), and **paper** (live data, internal fills, authoritative portfolio plus shadow books) — all sharing one domain core and one fill model.

### 1.1 Scope

- US liquid equities, end-of-day signals
- Weekly rebalance + daily risk checks
- Internal paper portfolio + shadow ablation books
- Full decision lineage and user education

### 1.2 Non-Goals (v1)

- Live brokerage execution (a broker port exists with `FakeBroker` and `AlpacaBroker` adapters, but live execution is out of v1 scope)
- Intraday trading, options/derivatives, shorting
- ML models, multi-agent coordination
- LLM-computed numbers anywhere

## 2. Architecture Principles

| # | Principle | Description |
|---|-----------|-------------|
| P1 | **Ports-and-Adapters** | `domain/` imports nothing from `adapters/` or `data/`. Pure domain core with fixture-backed fake adapters for deterministic replay. |
| P2 | **Three Realities, One Core** | Backtest, replay, and paper share the same domain functions and fill model. Comparability by construction. |
| P3 | **Clock Virtualization** | Clock port is fully wired — every app-layer consumer and domain function receives a `Clock` instance. `SystemClock` (live), `VirtualClock` (replay/backtest). Enables deterministic replay and golden CI. |
| P4 | **LLM is Explainer Only** | Never in the decision path. Every number is injected; a post-render checker verifies figures match source data. |
| P5 | **Degrade, Never Block** | Source failures degrade (not block) the pipeline. Only price staleness sets `DATA_HALT`. |
| P6 | **Append-Only Immutability** | Raw vault is append-only, zstd-compressed. Nothing is ever deleted or rewritten. |
| P7 | **Self-Consistency Over Reconciliation** | Nightly assertions over the DuckDB book. A violation is a software bug — full halt. |
| P8 | **13 System Invariants (I1–I13)** | Assertion-enforced properties. See DESIGN.md §16 for the authoritative invariant list with full descriptions. |

## 3. C4 Model

Six diagrams model the system at Levels 1–4 of the C4 model, rendered via LikeC4 DSL.

| Level | Diagram | Source | Description |
|-------|---------|--------|-------------|
| L1 | System Context | `views/systemContext.png` | System boundary, user, and all 6 external dependencies. |
| L2 | Container | `views/container.png` | 12 containers, 2 data stores, external systems. |
| L3 | Data Layer | `views/dataLayerComponents.png` | 7 components in the four-zone architecture. |
| L3 | Decision Engine | `views/decisionEngineComponents.png` | 8 mechanisms (M1–M8), position sizer, risk evaluator. |
| L3 | Fill Model & Portfolio | `views/fillModelPortfolioComponents.png` | 4 fill actions, portfolio, shadow books, consistency checker. |
| L4 | Deployment | `views/deployment.png` | Single-machine deployment with processes and storage. |

### 3.1 System Context (L1)

The user (retail investor) interacts with Alpha-Quant via CLI and Streamlit dashboard. The system fetches data from 6 external sources: **EODHD** (primary bars, fundamentals, earnings), **Alpaca Data** (quotes, calendar — data only, no trading), **SEC EDGAR** (company ticker mapping), **OpenInsider** (insider transactions), **Reddit** (mention counts for crowding veto), and **LLM Provider** (OpenAI/OpenRouter for narration).

### 3.2 Container Diagram (L2)

Alpha-Quant contains 13 containers and 2 internal data stores:

- **CLI** — argparse-based entry point for all operations
- **Pipeline Engine** — APScheduler-driven daily orchestrator (17:30 ET)
- **Data Layer** — Four zones: connectors → vault → canonical store → derived state
- **Domain Core** — Pure functions: M1–M8, position sizing, risk management
- **Fill Model** — Pessimistic fill semantics shared by all execution realities
- **Paper Portfolio** — Authoritative internal portfolio (transactional DuckDB)
- **Shadow Books** — 3 ablation books + SPY baseline
- **Narrator** — LLM-powered journal generation
- **Dashboard** — Streamlit read-only monitoring
- **Event Log** — Append-only typed event stream
- **DuckDB State Store** — Transactional state (ACID)
- **Parquet Archive** — Analytical data (date-partitioned)

### 3.3 Component Diagrams (L3)

**Data Layer** (7 components): Connectors (5 implementations sharing httpx + tenacity), Raw Vault (append-only zstd), Normalizer (pydantic parsers), Canonical Writer (PyArrow), Derive Engine (numpy indicator recurrences), Validator (~15 predicate checks), Catalog (versioning/manifest).

**Decision Engine** (10 components): M1 Universe, M2 Regime, M3 Technical, M4 Quality, M5 Insider, M6 Crowding, M7 Blackout, M8 Ranker, Position Sizer, Risk Evaluator. Gates are hard filters; scores feed the composite M8 rank.

**Fill Model & Portfolio** (8 components): Fill Entry, Fill Stop, Fill Partial Take, Fill Corporate Action, Paper Portfolio State, Shadow Books (x3), SPY Baseline, Self-Consistency Checker.

### 3.4 Deployment Diagram (L4)

Single-machine deployment with 3 processes (APScheduler Scheduler, CLI, Streamlit Dashboard) and 5 storage locations (Vault Directory, Canonical Directory, DuckDB State Database, Config File, Halt Lockfile). All processes share the local filesystem; the dashboard reads DuckDB concurrently.

## 4. Technology Stack

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Runtime | Python 3.14 | Latest stable; all core deps provide 3.14 wheels |
| Package manager | uv | Rust-based, 10-100x faster resolution, deterministic lockfile |
| HTTP client | httpx | Sync+async, HTTP/2, configurable timeouts |
| Retry/backoff | tenacity | Declarative per-connector policies |
| HTML parsing | selectolax | Fast, lenient; lxml fallback |
| Validation | pydantic v2 | Parse-don't-validate at zone boundaries |
| Analytical SQL | DuckDB | Zero-ops parquet queries, embedded |
| Columnar storage | PyArrow / Parquet (zstd) | Standard columnar format |
| State store | DuckDB | Both analytical (Parquet) and transactional (DuckDB) |
| Indicators | numpy recurrences (~100 lines) | O(1) per symbol per day |
| Scheduling | APScheduler (cron fallback) | In-process, simple |
| Configuration | pydantic-settings + TOML | Typed, env-overridable, SecretStr |
| Logging | structlog (JSON) | Events + logs share shape |
| Testing | pytest | Golden replay, integration tests, unit tests |
| LLM client | Direct httpx (no SDK) | Single adapter for OpenAI + OpenRouter |
| Market data | alpaca-py (data module only) | Trading module never imported |
| Dashboard | Streamlit | Read-only, zero pipeline coupling |
| CLI | argparse (stdlib) | Zero additional deps |
| Diagramming | LikeC4 | DSL-driven C4 diagrams, PNG export |

## 5. Architecture Decision Records

31 ADRs document every technology and architectural decision.

| ADR | Title | Key Decision |
|-----|-------|-------------|
| 0001 | Python 3.14 as Runtime | Chose 3.14 over 3.12 for actual dev environment wheel support |
| 0002 | uv as Package Manager | Chose uv over pip/Poetry for 10-100x faster CI |
| 0003 | Ports-and-Adapters Architecture | Chose hexagonal over layered/Clean for domain purity |
| 0004 | argparse for CLI | Chose stdlib over Click/Typer for zero-dependency CLI |
| 0005 | pydantic-settings + TOML | Chose over dynaconf/YAML for type-safe env overrides |
| 0006 | DuckDB + Parquet for Analytics | Chose over PostgreSQL/pandas for zero-ops columnar queries |
| 0007 | SQLite WAL + SQLAlchemy Core | **Superseded** — replaced by ADR-0021 |
| 0008 | Custom numpy Indicator Recurrences | Chose over TA-Lib/pandas-ta for O(1) incremental update |
| 0009 | Custom Pessimistic Fill Model | Chose for honest upper-bound simulation (gap-through-stop fills at open) |
| 0010 | Custom Event-Driven Backtester | Chose over vectorbt/Zipline for path-dependent portfolio |
| 0011 | Direct httpx for LLM | Chose over OpenAI SDK for single code path |
| 0012 | EODHD as Primary Data Source | Chose for bars+fundamentals+earnings in one API |
| 0013 | structlog JSON Logging | Chose for events+logs sharing shape |
| 0014 | Streamlit Dashboard | Chose over Panel/Grafana for fastest functional path |
| 0015 | Incremental O(1) Indicator Engine | O(1) per symbol; cold start via bootstrap |
| 0016 | Degrade-Don't-Block Data Failure | Source degradation with defined fallbacks |
| 0017 | Golden Replay as CI Strategy | SHA256 decision log comparison for deterministic replay |
| 0018 | Bootstrap + Fixture Bundle Workflow | One-time fetch freezes fixture bundle for offline dev/CI |
| 0019 | Astral Development Tooling (ruff + ty) | Lint/format/type from one toolchain |
| 0020 | DuckDB for Vault Manifest | DuckDB dual-use: vault manifest + analytical |
| 0021 | DuckDB for Both State Types | Unify analytical and transactional on DuckDB |
| 0022 | Paper Portfolio Engine | Authoritative portfolio state manager |
| 0023 | Pipeline Orchestrator | Daily run sequencing |
| 0024 | Self-Consistency Invariants | Portfolio integrity assertions |
| 0025 | SQLite Cache for SEC Connector | Per-connector SEC ticker cache |
| 0026 | Content-Addressed Vault | Append-only zstd blob storage |
| 0027 | Dependency Pruning | Remove polars, SQLAlchemy, 50-day prune |
| 0028 | Clock Virtualization | SystemClock + VirtualClock for deterministic replay |
| 0029 | Store Mixin Decomposition | 9 single-concern mixin files for CanonicalStore |
| 0030 | Shadow Ablation Books | Parallel portfolios for mechanism evaluation |
| 0031 | File-Based Halt Mechanism | Crash-safe .HALT file protocol |

See [docs/adr/README.md](../adr/README.md) for full ADR index.

## 6. Key Architecture Decisions

### 6.1 Pessimistic Fill Model (ADR-0009)

The most distinctive architectural decision. Unlike backtesting libraries that fill stops at the stop price or naive models that fill at the close, Alpha-Quant's fill model:
- **Gap-through-stops**: if `bar.low <= stop_price`, fills at `min(open, stop_price) - slippage`
- **Gap-up entries**: cancels if the open gaps >0.2% above the decision quote
- **Variable slippage**: rate-dependent (0.05–0.15%) with floor/ceiling

This ensures paper performance is an upper bound on achievable live results.

### 6.2 Degrade-Don't-Block (ADR-0016)

Each source has a defined fallback when unavailable:
- Insider data missing → M5 boost = 0 (no insider edge that day)
- Reddit data stale → M6 veto = fail-open (no crowding-based blocks)
- Earnings calendar unavailable → blackout window widens by 1 day
- Only price staleness (bars not updated for 2+ trading days) sets `DATA_HALT`

### 6.3 Golden Replay CI (ADR-0017)

The primary CI strategy is a full-DAG replay against 6 months of fixture data. The SHA256 hash of the decision log + equity curve must match a committed golden file. Because of determinism (I7), the replay is never flaky. Changes that alter behavior intentionally update the golden hash in the same PR via `make bless-golden`.

### 6.4 Three Execution Realities (P2)

Backtest, replay, and paper share one domain core and one fill model. The primary differences are:
- **Clock**: system clock (paper) vs. virtual clock (replay/backtest)
- **Data source**: live feeds (paper) vs. fixture vault (replay) vs. historical archive (backtest)
- **Speed**: wall-clock (paper) vs. as-fast-as-possible (replay/backtest)

## 7. Testing Strategy

| Layer | Speed | What | Tooling |
|-------|-------|------|---------|
| Domain unit tests | ms | Pure function invariants (I1–I13) | pytest |
| Full-DAG golden replay | s–min | 6-month fixture replay, hash comparison | CLI replay |
| Source degradation chaos | s | Fallback behavior verification | Synthetic overlays |
| 10-year backtest | <60s | Historical walk-forward | CLI backtest |

Every mechanism must show non-negative walk-forward Sharpe impact or be flagged off. Fixture bundles include synthetic overlays (missing-bar, stale-feed, mention spike) for edge-case coverage.

## 8. Deployment Model

Single-machine, zero-server deployment on a developer workstation or headless server. The daily pipeline runs at **17:30 ET** via APScheduler (cron fallback) in 9 sequential steps:

1. Ingest — EODHD delta, fundamentals, earnings, OpenInsider, Reddit, SEC map (weekly)
2. Validate — gaps/staleness/splits → `DATA_HALT`?
3. Derive — incremental indicator state, month-end calc
4. Regime — M2 classification
5. Risk — stops/trails/time-stops/drawdown ladder
6. Decide — gates M1, M4, M6, M7 → scores M3, M5 → M8 ranking
7. Simulate — queue T+1 orders for paper + shadow books
8. Persist — decisions, lineage
9. Narrate — daily journal (LLM-polished, fact-checked)

At the next open: fill queued orders against T+1 bars.

### 8.1 Data Layout

- Raw vault: `vault/{source}/{yyyy}/{mm}/{dd}/{fetch_id}.zst`
- Canonical data: `canonical/bars/date=*/` (Parquet, date-partitioned)
- Transactional state: `data/state.db` (DuckDB)

### 8.2 Operational Controls

- **Halt**: `alpha-quant halt` creates a lockfile that blocks the scheduler
- **Backup**: DuckDB state store copy + vault sync
- **Monitoring**: alerts on data staleness, source degradation, consistency violations
- **Chaos testing**: kill mid-run, restart, verify idempotency; forced staleness → halt + alert

### 8.3 Migration Path (post-v1)

- DuckDB state store → PostgreSQL behind the `store` port
- Local Parquet → S3/MinIO behind DuckDB path config
- Paper engine → live broker via `broker.py` port (defined; adapters exist, live execution is out of v1 scope)

## 9. Related Documents

- [DESIGN.md](../../DESIGN.md) — Detailed system design specification (v1.2)
- [Model DSL](model.c4) — LikeC4 model definitions (all elements, relationships, deployment)
- [Views DSL](views.c4) — LikeC4 view definitions (6 diagram layouts)
- [ADR Index](../adr/README.md) — 31 Architecture Decision Records
- [ROADMAP.md](../planning/ROADMAP.md) — 6-phase implementation timeline
- [BACKLOG.md](../planning/BACKLOG.md) — Full backlog with epics and stories

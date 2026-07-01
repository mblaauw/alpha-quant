# Alpha-Quant — Reference Architecture

## 1. System Context

Alpha-Quant is a **deterministic strategy-policy and paper-trading engine**. It consumes point-in-time market facts exclusively from **Alpha-Lake** through a versioned authenticated REST API. Alpha-Quant owns decisions, portfolio controls, paper execution, journals, and replay — not market data.

### External Dependencies

| Dependency | Purpose | Protocol |
|------------|---------|----------|
| Alpha-Lake | All market facts (bars, indicators, fundamentals, insider, earnings, attention) | HTTPS REST (PIT `as_of` + optional `snapshot_id`) |
| PostgreSQL 17+ | Operational system of record (decision runs, candidates, orders, fills, marks, halts) | psycopg 3 / SQLAlchemy 2 Core |
| S3-compatible | Artifact store for decision evidence (SHA-256 verified) | HTTPS (boto3) |
| OpenRouter/OpenAI (optional) | LLM narration and decision explanations | HTTPS REST |

### Non-Goals

- Market data ingestion, normalization, or storage
- Technical indicator calculation
- Fundamental ratio computation
- Sentiment/mention aggregation
- Source-provider management (EODHD, SEC, OpenInsider, Reddit)
- Live brokerage execution

## 2. Architecture Style

**Ports-and-Adapters (Hexagonal).** The domain boundary is `ports/alpha_lake.py:AlphaLakeReadPort` — all market facts flow through a single authenticated REST interface. The operational system of record is `ports/operational_store.py:OperationalStorePort` — a PostgreSQL-backed append-only ledger with rebuildable projections. Scorecards, advice artifacts, and explanations are persisted directly in PostgreSQL via the operational store.

## 3. Module Layout

```
src/alpha_quant/
├── contracts/
│   ├── alpha_lake.py             # FactsBundle data contracts (frozen Pydantic)
│   └── operational.py            # Frozen dataclass contracts for PostgreSQL operational store
├── domain/
│   ├── _base.py                  # Shared FrozenModel base class
│   ├── models.py                 # Bar, Position, Order, Fill, Decision, Candidate, PortfolioSnapshot (frozen Pydantic)
│   ├── events.py                 # DomainEvent types (regressed to plain dict)
│   ├── risk.py                   # RiskPolicy, RiskCalculation, RiskDecision (unified policy model)
│   ├── scorecard.py              # Scorecard, ComponentState, Recommendation, StageResult
│   ├── advice.py                 # AdviceArtifact, AdviceRecommendation, ExplanationScope, OperatorOverride
│   ├── categories.py             # Module-to-category mapping
│   ├── calendar.py               # Market calendar utilities
│   └── regime.py                 # Regime literal type
├── ports/
│   ├── alpha_lake.py             # AlphaLakeReadPort (Protocol): read_facts_bundle → FactsBundle
│   ├── operational_store.py      # OperationalStorePort (Protocol): 33 methods for PostgreSQL
│   ├── clock.py                  # Clock port
│   └── llm.py                    # LLM port
├── adapters/
│   ├── _parse.py                 # Shared parsing helpers for Alpha-Lake responses
│   ├── postgres/                 # PostgreSQL adapters
│   │   ├── tables.py             # ORM models across 6 schemas (core, run, trade, projection, audit, ops)
│   │   ├── engine.py             # Engine + session factory + init_schema()
│   │   ├── health.py             # Health check
│   │   ├── operational_store.py  # PostgresOperationalStore (SQLAlchemy Core text)
│   │   └── unit_of_work.py       # OperationalUnitOfWork context manager
│   ├── real/
│   │   ├── alpha_lake_rest.py    # AlphaLakeRestClient (httpx → Alpha-Lake REST API)
│   │   ├── clock.py              # SystemClock
│   │   └── llm_adapter.py        # OpenAILikeLLM
│   └── fake/
│       ├── alpha_lake_http_fixture.py  # Offline replay from fixture files
│       ├── operational_store.py        # In-memory fake for unit tests
│       ├── unit_of_work.py       # FakeUnitOfWork for tests
│       ├── virtual_clock.py      # Deterministic clock for tests
│       └── canned_llm.py         # Static LLM responses for tests
├── transport/
│   ├── app.py                    # FastAPI BFF with CORS, static mounts, health, console routes, commands, MCP
│   ├── health.py                 # /livez, /readyz endpoints
│   ├── console_routes.py         # /v1/* console API (equity, positions, runs, decisions, scorecards, advice, risk, journal, orders, system, freshness)
│   ├── commands.py               # /v1/commands CRUD + cancel API
│   ├── deps.py                   # FastAPI dependency injection helpers
│   └── static/                   # Vanilla JS SPA
│       ├── index.html            # Application shell
│       ├── styles.css            # CSS custom properties design system
│       ├── app.js                # Entry point with routing, polling, event handling
│       ├── state.js              # Explicit application state object
│       ├── router.js             # Hash-based client-side router
│       ├── api.js                # Fetch API wrapper with idempotency headers
│       ├── commands.js           # Command confirmation modal workflow
│       ├── formatters.js         # Shared display formatters
│       ├── freshness.js          # Freshness status indicator
│       ├── render/               # View renderers (advice, decisions, drawers, orders, portfolio, risk, shell, system)
│       └── components/           # Reusable UI components (banner, drawer, empty_state, error_state, modal, status, table, toast, tooltip)
├── application/
│   ├── cli.py                    # Typer CLI: db-*, dashboard, worker
│   ├── config.py                 # pydantic-settings AppConfig with nested configs
│   ├── factory.py                # Composition root: create_alpha_lake_reader, create_llm, create_clock, create_unit_of_work, run_migrations, seed_default_data
│   ├── daily_cycle.py            # DailyCycleService — pipeline orchestrator (scorecard decision cycle with FactsBundle)
│   ├── scorecards.py             # Scorecard engine — M1–M8 evaluation (1126 lines)
│   ├── explanation.py            # LLM explanation service (479 lines)
│   ├── prompts.py                # LLM prompt templates
│   ├── alerts.py                 # System alert management
│   ├── dev_seed.py               # Dev seed data for development/testing
│   ├── import_legacy_duckdb.py   # One-time DuckDB → PostgreSQL migration tool
│   ├── query/                    # Query service layer (10 domain services, PostgreSQL-backed)
│   │   ├── decisions.py, freshness.py, journal.py, orders.py
│   │   ├── portfolio.py, risk.py, runs.py, scorecards.py
│   │   ├── shared.py, system.py
│   ├── risk/                     # Risk engine (10 modules)
│   │   ├── component.py, concentration.py, factors.py, inputs.py
│   │   ├── limits.py, liquidity.py, methods.py, posture.py
│   │   ├── scenarios.py, var.py
│   └── commands/                 # Durable command model + handler dispatcher
└── migrations/                   # Alembic migrations (14 versions)
    ├── env.py
    ├── script.py.mako
    └── versions/
        ├── 0001_schema_baseline.py   # Schema baselines
        ├── 0002_command_table.py      # ops.command table
        ├── 0003_scorecards_advice_risk.py
        ├── 0004_nullable_order_decision_fk.py
        ├── 0005_book_risk_profile_and_constraints.py
        ├── 0006_check_constraints_and_enums.py
        ├── 0007_enum_check_constraints.py
        ├── 0008_app_config_table.py
        ├── 0009_fix_audit_event_nullable.py
        ├── 0010_risk_policy_version.py
        ├── 0011_advice_artifact_columns.py
        ├── 0012_explanation_columns.py
        ├── 0013_explanation_persist_fields.py
        └── 0014_explanation_constraints.py
```

## 4. Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Runtime | Python 3.14 | Type hints, pattern matching, free-threaded |
| HTTP Client | httpx | Async-capable, connection pooling, timeout support |
| Operational Store | PostgreSQL 17+ (psycopg 3, SQLAlchemy 2 Core) | ACID-compliant system of record, append-only ledger |
| CLI | Typer + Rich | Type-hint-driven commands (db-*, dashboard, worker) |
| Dashboard | Vanilla JS SPA + FastAPI BFF | No build step, same-origin, same container |
| Type Checker | ty (Astral) | Fast, Python 3.14 compatible |
| Linter/Formatter | ruff (Astral) | Unified lint + format, 10-100x faster |
| Config | pydantic-settings + TOML | Type-safe environment overrides, nested sub-configs |
| Migrations | Alembic | Schema versioning for PostgreSQL |
| Frontend | Vanilla ES modules + CSS custom properties | No Node, no npm, no bundler |
| Domain Models | pydantic.BaseModel (frozen=True) | Immutable, validated, JSON-serializable |
| Data Contracts | frozen dataclasses | Lightweight, hashable, cross-boundary transfer types |

## 5. Architecture Decision Records

71 ADRs document every technology and architectural decision.

| ADR | Title | Status |
|-----|-------|--------|
| 0001 | Python 3.14 as Runtime | Accepted |
| 0002 | uv as Package Manager | Accepted |
| 0003 | Ports-and-Adapters Architecture | Accepted |
| 0005 | pydantic-settings + TOML Configuration | Accepted |
| 0011 | Direct httpx for LLM | Accepted |
| 0013 | structlog JSON Logging | Accepted |
| 0016 | Degrade-Don't-Block Failure Model | Accepted |
| 0017 | Golden Replay as CI Strategy | Accepted |
| 0019 | Astral Development Tooling (ruff + ty) | Accepted |
| 0028 | Clock Virtualization | Accepted |
| 0033 | Clock-Driven PIT Reads | Accepted |
| 0035 | Alpha-Lake REST Is the Sole Facts Plane | Accepted |
| 0036 | Neutral Facts in Alpha-Lake, Strategy Policy in Alpha-Quant | Accepted |
| 0037 | PostgreSQL as Operational System of Record | **Accepted** |
| 0038 | Append-Only Ledger with Rebuildable Projections | **Accepted** |
| 0040 | Database-Backed Halts and Transactional Run Locks | **Accepted** |
| 0041 | Migration Strategy — Consolidating to `src/alpha_quant/` | **Accepted** |
| 0042 | Static SPA and Same-Origin FastAPI BFF | **Accepted** |
| 0043 | Durable Command Model for Dashboard Mutations | **Accepted** |
| 0044 | Persistent Named Docker Volumes and Idempotent Migrations | **Accepted** |
| 0045 | No Offline Cache for the Write-Capable Operational Console | **Accepted** |
| 0046 | Static Lake Watch–Aligned Operational Console | **Accepted** |
| 0047 | Operational Context Is Not Global PIT Context | **Accepted** |
| 0048 | Commands Are the Sole Mutation Boundary | **Accepted** |
| 0049 | Alpha-Lake Facts Bundle as Primary Scorecard Data Source | Accepted |
| 0050 | Scorecards Are the Primary Decision Artifact | Accepted |
| 0051 | LLM Explains Deterministic Advice — Never Computes It | Accepted |
| 0052 | User Overrides Are Audited Commands | Accepted |
| 0053 | Risk Methods Are User-Visible Deterministic Policies | Accepted |
| 0054 | Desk Redesigned with Advice-First Tab | Accepted |
| 0056 | Real Risk Engine Replaces Placeholder Calculations | Accepted |
| 0057 | Scorecard Engine Replaces Policy Modules as Decision Core | Accepted |
| 0058 | Removal of CLI run/status/journal/ask/report/halt/backup Commands | Accepted |
| 0059 | DomainEvent Regression to Plain dict | Accepted |
| 0060 | Risk Engine Uses Synthetic Returns as v1 Methodology | Accepted |
| 0061 | DuckDB Retained for Legacy Import Only | Accepted |
| 0062 | Console Mutation Routes Reconciled with Command Bus | Accepted |
| 0063 | Unified Risk Policy Model Replaces Three Disconnected Systems | Accepted |
| 0064 | Scoring Policy Versioning via RiskPolicy.component_weights_json | Accepted |
| 0065 | LLM Integration and Guardrails for Deterministic Advice | Accepted |
| 0066 | FakeOperationalStore Enables Containerless Testing | Accepted |
| 0067 | LLM Explanation Boundary and Non-Authoritative Role | Accepted |
| 0068 | Calculation-Snapshot-Based Explanation Invalidation | Accepted |
| 0069 | Structured Output and Validation Contract for Explanations | Accepted |
| 0070 | Mock-First LLM Provider Strategy for Explanations | Accepted |
| 0071 | Explanation Persistence and Provenance | Accepted |
| 0004 | argparse for CLI | Superseded |
| 0006 | DuckDB + Parquet for Analytics | Superseded |
| 0007 | SQLite WAL + SQLAlchemy Core | Superseded |
| 0008 | Custom numpy Indicator Recurrences | Superseded |
| 0009 | Custom Pessimistic Fill Model | Superseded |
| 0010 | Custom Event-Driven Backtester | Superseded |
| 0012 | EODHD as Primary Data Source | Superseded |
| 0014 | Streamlit Dashboard | Superseded |
| 0015 | Incremental O(1) Indicator Engine | Superseded |
| 0018 | Bootstrap + Fixture Bundle Workflow | Superseded |
| 0020 | DuckDB for Vault Manifest | Superseded |
| 0021 | DuckDB for Both State Types | Superseded |
| 0022 | Paper Portfolio Engine | Superseded |
| 0023 | Pipeline Orchestrator | Superseded |
| 0024 | Self-Consistency Invariants | Superseded |
| 0025 | SQLite Cache for SEC Connector | Superseded |
| 0026 | Content-Addressed Vault | Superseded |
| 0027 | Dependency Pruning | Superseded |
| 0029 | Store Mixin Decomposition | Superseded |
| 0030 | Shadow Ablation Books | Superseded |
| 0031 | File-Based Halt Mechanism | Superseded |
| 0032 | Alpha-Lake Data Plane | Superseded |
| 0034 | LakeGateway Port | Superseded |
| 0039 | S3-Compatible Artifact Store | Superseded |
| 0055 | Risk Desk Placeholder Contract | Superseded |

See [docs/adr/README.md](../adr/README.md) for full ADR index with titles and dates.

## 6. Key Architecture Decisions

### 6.1 Single REST Facts Port (ADR-0035)

All market facts enter through `AlphaLakeReadPort` — one protocol, one implementation per environment:

- **Production:** `AlphaLakeRestClient` (httpx → Alpha-Lake REST API)
- **Test/Replay:** `AlphaLakeHttpFixtureClient` (pre-recorded HTTP responses)

No other runtime data-access mechanism exists. The old in-process lake gateway (ADR-0034) and DuckDB/Parquet data plane (ADR-0032) are superseded.

### 6.2 Facts Bundle Contract (ADR-0036, ADR-0049)

Alpha-Lake returns `FactsBundle` — pre-computed, versioned observations keyed by category. Scorecards consume facts; they never calculate neutral metrics locally:

```python
# Correct: scorecard reads pre-computed metric from FactsBundle
rsi = facts.get("momentum.rsi_14")
if rsi is not None and rsi > 70:
    return 0.0

# Wrong: never calculate RSI locally
# rsi = calc_rsi(bars, 14)  # forbidden
```

The contract is a Pydantic model containing pre-computed observations by category. Bars are provided solely for fill simulation and stop tracking — scorecards must not read bars directly.

### 6.3 PostgreSQL Operational System of Record (ADR-0037)

PostgreSQL 17+ replaces DuckDB as the authoritative operational store. The schema spans 25+ tables across 6 schemas:

| Schema | Tables | Purpose |
|--------|--------|---------|
| `core` | strategy, strategy_version, portfolio_book, security_reference, execution_profile | Static reference data |
| `run` | decision_run, alpha_lake_manifest, candidate_evaluation, policy_evaluation, scorecard, scorecard_component, advice_artifact | Decision run lifecycle + LLM advice |
| `trade` | paper_order, paper_fill, cash_ledger_entry, corporate_action_booking, portfolio_mark | Paper execution |
| `projection` | position_current, portfolio_current | Rebuildable read models |
| `audit` | audit_event, risk_event, halt_transition, operator_override | Append-only event log |
| `ops` | current_halt, run_lock_audit, command, app_config | Operational controls |

### 6.4 Append-Only Ledger with Rebuildable Projections (ADR-0038)

The trade and audit schemas are append-only. Current positions and portfolio state are `projection` tables rebuilt on demand from the raw ledger. `rebuild_projections()` replays all fills to reconstruct position_current and portfolio_current. This eliminates update-in-place anomalies and provides a complete audit trail.

### 6.5 Scorecard-Based Decision Core (ADR-0050, ADR-0057)

The scorecard engine (`application/scorecards.py`) replaces the old 7-policy-module architecture. Scorecards compute M1–M8 component scores, composite rank, and a final recommendation. Scorecards are persisted in `run.scorecard` and `run.scorecard_component` tables with full version tracking. The scoring policy includes versioned weights via `RiskPolicy.component_weights_json` (ADR-0064).

### 6.6 LLM Explanation Layer (ADR-0051, ADR-0065–0071)

The LLM explains deterministic advice — it never computes it. Explanations are generated on-demand, persisted in `run.advice_artifact`, and invalidated via calculation snapshots. A mock-first strategy (ADR-0070) enables containerless testing. Provenance tracking includes prompt version, input/output hashes, and validation status.

### 6.7 Point-in-Time (PIT) Determinism (ADR-0033)

Every decision, backtest, and replay run uses:
- `as_of` (mandatory): the knowledge-time boundary for all facts
- `snapshot_id` (mandatory for replay, recommended for backtests): pins to a specific Alpha-Lake catalog snapshot

This ensures byte-stable reproducibility: same config + same snapshot = same decisions.

### 6.8 Unified Risk Policy Model (ADR-0063)

A single `RiskPolicy` model (`domain/risk.py`) unifies all trading thresholds, limits, and decisions — replacing three disconnected systems (stop-loss config, drawdown ladder, position sizing). The risk engine (`application/risk/`) evaluates 10+ dimensions: component, concentration, factors, inputs, limits, liquidity, methods, posture, scenarios, and VaR.

### 6.9 Durable Command Model (ADR-0043, ADR-0048)

All dashboard mutations flow through the command bus (`ops.command` table). Commands are persisted, claimed via `SKIP LOCKED`, dispatched to typed handlers, and polled until terminal status. This provides exactly-once semantics and a full audit trail.

### 6.10 Vanilla JS Operational Console (ADR-0042, ADR-0046)

A FastAPI BFF + Vanilla JS SPA serves the operational console. No build step, no bundler — ES modules served directly. The console reads from PostgreSQL query services, not directly from DuckDB.

## 7. Runtime Flow

### Decision Run (via DailyCycleService)
```
1. External trigger: HTTP POST /v1/commands (decision_run.create) or cron
2. Command worker claims the command via SKIP LOCKED on ops.command
3. Factory: create_alpha_lake_reader(config) → AlphaLakeRestClient
4. Halt check: current_halt(book_id) → ops.current_halt table (ADR-0040)
5. Client: GET /v1/health → verify server readiness
6. Client: GET /v1/contract → verify version + capabilities
7. Reserve run: OperationalStorePort.reserve_run() → decision_run record
8. For each symbol in universe:
   a. Client: GET /v1/facts?symbol=X&as_of=T → FactsBundle
   b. Scorecard engine: evaluate M1–M8 components (application/scorecards.py)
   c. Persist: candidate_evaluation, policy_evaluation, scorecard_component
9. Composite ranking and final recommendation
10. Risk engine: evaluate portfolio-level limits (gross exposure, VaR, concentration, liquidity)
11. Position sizing: apply RiskPolicy thresholds
12. Book fills via OperationalStorePort.book_fill()
13. Persist scorecard, advice artifacts via OperationalStorePort
14. Mark portfolio, rebuild projections
15. Complete run
```

### Dashboard Mutation Flow
```
1. Browser POST /v1/commands with command envelope + idempotency_key
2. submit_command() persists command to ops.command table
3. Audit event recorded: command.{type}.requested
4. Worker claims command via SKIP LOCKED
5. Dispatcher routes to typed handler (halt.create, decision_run.create, etc.)
6. Handler executes domain operation
7. Command result persisted (succeeded/failed)
8. UI polls GET /v1/commands/{id} until terminal status
9. UI fetches affected read model and renders committed state
```

### Worker Lifecycle
```
1. alpha-quant worker starts
2. Polls ops.command for status=queued rows via SKIP LOCKED
3. Claims one command, sets status=running
4. Dispatches to command handler
5. Handler executes (synchronous, within worker process)
6. Writes result (succeeded/failed/cancelled)
7. Repeats or sleeps based on poll_interval
```

## 8. Configuration

```toml
[lake]
mode = "rest"
base_url = "http://alpha-lake:8000"
api_key_env = "ALPHA_LAKE_API_KEY"
fixture_version = "v1"

[data]
mode = "live"
fixture_version = "v1"

[risk]
version_label = "default"
stop_atr_mult = 2.0
trail_after_r = 1.0
partial_take_at_r = 2.0
time_stop_days = 30
dd_ladder = [[0.10, 0.5], [0.15, 0.0]]
drawdown_limit = -0.10
daily_loss_limit = -0.02
daily_loss_halt_pct = 0.03
gross_exposure_cap = 0.90
sector_cap = 0.70
single_name_cap = 0.25
default_risk_pct = 0.005
buying_power_pct = 0.18
per_trade_risk_cap = 0.01

[llm]
provider = "openrouter"
model = "anthropic/claude-sonnet-4"
timeout_s = 30

[freshness]
sla_minutes = 120
critical_minutes = 1440
gate_live_decisions = true
```

## 9. Related Documents

- [ADR Index](../adr/README.md) — 71 ADRs
- [DESIGN.md](../DESIGN.md)
- [Alpha-Lake API Documentation](https://github.com/mblaauw/alpha-lake)

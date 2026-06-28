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

**Ports-and-Adapters (Hexagonal).** The domain boundary is `ports/alpha_lake.py:AlphaLakeReadPort` — all market facts flow through a single authenticated REST interface. The operational system of record is `ports/operational_store.py:OperationalStorePort` — a PostgreSQL-backed append-only ledger with rebuildable projections. Artifact storage is `ports/artifact_store.py:ArtifactStorePort` — an S3-compatible store with content-addressable keys and SHA-256 verification.

## 3. Module Layout

```
src/alpha_quant/
├── contracts/
│   ├── alpha_lake.py             # NeutralObservation data contracts (frozen dataclasses)
│   └── operational.py            # 25 frozen dataclass contracts for PostgreSQL operational store
├── domain/
│   ├── decision_context.py       # DecisionContext wrapping NeutralObservations
│   ├── policy/                   # 7 policy modules
│   │   ├── regime_policy.py, technical_policy.py, fundamental_policy.py
│   │   ├── insider_policy.py, attention_policy.py
│   │   ├── earnings_blackout_policy.py, composite_policy.py
│   ├── models.py                 # Bar, Position, Order, Fill, Decision, Candidate, PortfolioSnapshot (frozen Pydantic)
│   ├── events.py                 # 20+ DomainEvent types (discriminated union)
│   ├── fills.py                  # FillConfig, fill_entry_order, fill_stop_loss, fill_partial_take
│   ├── risk.py                   # RiskConfig, evaluate_stops, evaluate_drawdown, evaluate_daily_loss
│   ├── sizing.py                 # SizingConfig, size_position
│   ├── ranking.py                # Candidate ranking with sector diversification
│   ├── invariants.py             # Self-consistency invariant checks
│   └── narration.py, journal.py, reporting.py, calendar.py, ask.py, degradation.py, regime.py, constants.py
├── ports/
│   ├── alpha_lake.py             # AlphaLakeReadPort (Protocol): read_observations → NeutralObservations
│   ├── operational_store.py      # OperationalStorePort (Protocol): 20 methods for PostgreSQL
│   ├── artifact_store.py         # ArtifactStorePort (Protocol): put_json, get_json, verify
│   ├── store.py                  # Legacy Store port (DuckDB)
│   ├── clock.py                  # Clock port
│   ├── event_sink.py             # EventSink port
│   └── llm.py                    # LLM port
├── adapters/
│   ├── _parse.py                 # Shared parsing helpers for Alpha-Lake responses
│   ├── postgres/                 # PostgreSQL adapters
│   │   ├── tables.py             # 21 ORM models across 6 schemas (core, run, trade, projection, audit, ops)
│   │   ├── engine.py             # Engine + session factory + init_schema()
│   │   ├── health.py             # Health check
│   │   ├── operational_store.py  # PostgresOperationalStore (20 methods, SQLAlchemy Core text)
│   │   └── unit_of_work.py       # OperationalUnitOfWork context manager
│   ├── artifacts/
│   │   └── s3_artifact_store.py  # S3 artifact store with SHA-256 verification
│   ├── real/
│   │   ├── alpha_lake_rest.py    # AlphaLakeRestClient (httpx → Alpha-Lake REST API)
│   │   ├── clock.py              # SystemClock
│   │   ├── event_sink.py         # DuckDBEventSink
│   │   └── llm_adapter.py        # OpenAILikeLLM
│   └── fake/
│       ├── alpha_lake_http_fixture.py  # Offline replay from fixture files
│       ├── fake_operational_store.py   # In-memory fake for unit tests
│       ├── fixture_store.py      # FixtureStore for test replay
│       ├── virtual_clock.py      # Deterministic clock for tests
│       ├── canned_llm.py         # Static LLM responses for tests
│       └── fake_event_sink.py    # In-memory event sink for tests
├── transport/
│   ├── app.py                    # FastAPI BFF with CORS, static mounts, health, dashboard, and command routes
│   ├── health.py                 # /livez, /readyz endpoints
│   ├── dashboard.py              # Router aggregation for /v1/dashboard/*
│   ├── commands.py               # /v1/commands CRUD + cancel API
│   ├── handlers/                 # Transport handler modules (command_center, decisions, portfolio, orders, risk, runs, journal, reports, system, halts)
│   └── static/                   # Vanilla JS SPA
│       ├── index.html            # Application shell
│       ├── styles.css            # CSS custom properties design system
│       ├── app.js                # Entry point with routing, polling, event handling
│       ├── state.js              # Explicit application state object
│       ├── router.js             # Hash-based client-side router
│       ├── api.js                # Fetch API wrapper with idempotency headers
│       ├── commands.js           # Command confirmation modal workflow
│       ├── render/               # 9 view renderers (command_center, decisions, portfolio, orders, risk, runs, journal, reports, system)
│       └── components/           # Reusable UI components (cards, table, drawer, modal, tooltip, empty_state, loading_state)
├── application/
│   ├── cli.py                    # Typer CLI: run, journal, ask, report, status, halt, backup, db-*, dashboard, worker
│   ├── config.py                 # pydantic-settings AppConfig with nested configs
│   ├── factory.py                # Composition root: create_alpha_lake_reader, create_event_sink, create_store, create_llm, create_clock, create_unit_of_work, run_migrations, seed_default_data
│   ├── pipeline_v2.py            # Pipeline orchestrator (daily decision cycle with NeutralObservations)
│   ├── halt.py                   # Database-backed halt via ops.current_halt (ADR-0040)
│   ├── backup.py                 # DuckDB state store backup
│   ├── alerts.py                 # System alert management
│   ├── catalog.py                # Data catalog queries
│   ├── import_legacy_duckdb.py   # One-time DuckDB → PostgreSQL migration tool
│   ├── query/                    # Query service layer (9 domain services, PostgreSQL-backed)
│   ├── commands/                 # Durable command model + handler dispatcher
│   └── store/                    # CanonicalStore (DuckDB legacy — being replaced)
│       ├── state.py              # CanonicalStore base + schema init
│       └── *mixins               # PositionStore, OrderStore, DecisionStore, EventStore, JournalStore, AdminStore
└── migrations/                   # Alembic migrations
    ├── env.py
    └── versions/
        ├── 0001_schema_baseline.py  # 21 tables across 6 schemas
        └── 0002_command_table.py     # ops.command table for durable commands
```

## 4. Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Runtime | Python 3.14 | Type hints, pattern matching, free-threaded |
| HTTP Client | httpx | Async-capable, connection pooling, timeout support |
| Operational Store | PostgreSQL 17+ (psycopg 3, SQLAlchemy 2 Core) | ACID-compliant system of record, append-only ledger |
| Artifact Store | S3-compatible (boto3) | Durable, content-addressed, SHA-256 verified decision evidence |
| CLI | Typer + Rich | Type-hint-driven commands, formatted tables, panels |
| Dashboard | Vanilla JS SPA + FastAPI BFF | No build step, same-origin, same container |
| Type Checker | ty (Astral) | Fast, Python 3.14 compatible |
| Linter/Formatter | ruff (Astral) | Unified lint + format, 10-100x faster |
| Config | pydantic-settings + TOML | Type-safe environment overrides, nested sub-configs |
| Migrations | Alembic | Schema versioning for PostgreSQL |
| Frontend | Vanilla ES modules + CSS custom properties | No Node, no npm, no bundler |
| Domain Models | pydantic.BaseModel (frozen=True) | Immutable, validated, JSON-serializable |
| Data Contracts | frozen dataclasses | Lightweight, hashable, cross-boundary transfer types |

## 5. Architecture Decision Records

45 ADRs document every technology and architectural decision.

| ADR | Title | Status |
|-----|-------|--------|
| 0001 | Python 3.14 as Runtime | Accepted |
| 0002 | uv as Package Manager | Accepted |
| 0003 | Ports-and-Adapters Architecture | Accepted |
| 0005 | pydantic-settings + TOML Configuration | Accepted |
| 0009 | Custom Pessimistic Fill Model | Accepted |
| 0010 | Custom Event-Driven Backtester | Accepted |
| 0011 | Direct httpx for LLM | Accepted |
| 0013 | structlog JSON Logging | Accepted |
| 0014 | Streamlit Dashboard | **Superseded** (by FastAPI dashboard) |
| 0016 | Degrade-Don't-Block Failure Model | Accepted |
| 0017 | Golden Replay as CI Strategy | Accepted |
| 0019 | Astral Development Tooling (ruff + ty) | Accepted |
| 0021 | DuckDB for Both State Types | Accepted |
| 0022 | Paper Portfolio Engine | Accepted |
| 0023 | Pipeline Orchestrator | Accepted |
| 0024 | Self-Consistency Invariants | Accepted |
| 0027 | Dependency Pruning | Accepted |
| 0028 | Clock Virtualization | Accepted |
| 0029 | Store Mixin Decomposition | Accepted |
| 0030 | Shadow Ablation Books | Accepted |
| 0031 | File-Based Halt Mechanism | **Superseded** (by ADR-0040) |
| 0033 | Clock-Driven PIT Reads | Accepted |
| 0035 | Alpha-Lake REST Is the Sole Facts Plane | Accepted |
| 0036 | Neutral Facts in Alpha-Lake, Strategy Policy in Alpha-Quant | Accepted |
| 0037 | PostgreSQL as Operational System of Record | **Accepted** |
| 0038 | Append-Only Ledger with Rebuildable Projections | **Accepted** |
| 0039 | S3-Compatible Artifact Store | **Accepted** |
| 0040 | Database-Backed Halts and Transactional Run Locks | **Accepted** |
| 0041 | Migration Strategy — Consolidating to `src/alpha_quant/` | **Accepted** |
| 0042 | Static SPA and Same-Origin FastAPI BFF | **Accepted** |
| 0043 | Durable Command Model for Dashboard Mutations | **Accepted** |
| 0044 | Persistent Named Docker Volumes and Idempotent Migrations | **Accepted** |
| 0045 | No Offline Cache for the Write-Capable Operational Console | **Accepted** |
| 0004 | argparse for CLI | Superseded |
| 0006 | DuckDB + Parquet for Analytics | Superseded |
| 0007 | SQLite WAL + SQLAlchemy Core | Superseded |
| 0008 | Custom numpy Indicator Recurrences | Superseded |
| 0012 | EODHD as Primary Data Source | Superseded |
| 0015 | Incremental O(1) Indicator Engine | Superseded |
| 0018 | Bootstrap + Fixture Bundle Workflow | Superseded |
| 0020 | DuckDB for Vault Manifest | Superseded |
| 0025 | SQLite Cache for SEC Connector | Superseded |
| 0026 | Content-Addressed Vault | Superseded |
| 0032 | Alpha-Lake Data Plane | Superseded |
| 0034 | LakeGateway Port | Superseded |

See [docs/adr/README.md](../adr/README.md) for full ADR index with titles and dates.

## 6. Key Architecture Decisions

### 6.1 Single REST Facts Port (ADR-0035)

All market facts enter through `AlphaLakeReadPort` — one protocol, one implementation per environment:

- **Production:** `AlphaLakeRestClient` (httpx → Alpha-Lake REST API)
- **Test/Replay:** `AlphaLakeHttpFixtureClient` (pre-recorded HTTP responses)

No other runtime data-access mechanism exists. The old in-process lake gateway (ADR-0034) and DuckDB/Parquet data plane (ADR-0032) are superseded.

### 6.2 Neutral Observation Contract (ADR-0036)

Alpha-Lake returns `NeutralObservations` — pre-computed, versioned observations. Policies never recalculate a neutral metric:

```python
# Correct: policy applies threshold to Alpha-Lake metric
rsi = context.indicator("momentum.rsi_14")
if rsi is not None and rsi > 70:
    return 0.0

# Wrong: never calculate RSI locally
# rsi = calc_rsi(bars, 14)  # forbidden
```

The contract is a frozen dataclass hierarchy: `NeutralObservations` → `SymbolObservations` → `PriceObservation | TechnicalObservations | FundamentalMetric | InsiderTransaction | EarningsEvent | MentionObservation | BarObservation`. Bars are provided solely for fill simulation and stop tracking — policies must not read bars directly.

### 6.3 PostgreSQL Operational System of Record (ADR-0037)

PostgreSQL 17+ replaces DuckDB as the authoritative operational store. The schema spans 21 tables across 6 schemas:

| Schema | Tables | Purpose |
|--------|--------|---------|
| `core` | strategy, strategy_version, portfolio_book, security_reference, execution_profile | Static reference data |
| `run` | decision_run, alpha_lake_manifest, candidate_evaluation, policy_evaluation | Decision run lifecycle |
| `trade` | paper_order, paper_fill, cash_ledger_entry, corporate_action_booking, portfolio_mark | Paper execution |
| `projection` | position_current, portfolio_current | Rebuildable read models |
| `audit` | audit_event, risk_event, halt_transition | Append-only event log |
| `ops` | current_halt, run_lock_audit | Operational controls |

### 6.4 Append-Only Ledger with Rebuildable Projections (ADR-0038)

The trade and audit schemas are append-only. Current positions and portfolio state are `projection` tables rebuilt on demand from the raw ledger. `rebuild_projections()` replays all fills to reconstruct position_current and portfolio_current. This eliminates update-in-place anomalies and provides a complete audit trail.

### 6.5 S3-Compatible Artifact Store (ADR-0039)

Decision evidence (JSON blobs) is stored in an S3-compatible bucket with SHA-256 content hashing. Each artifact is immutable and independently verifiable. The `ArtifactStorePort` protocol exposes `put_json`, `get_json`, and `verify` methods.

### 6.6 Point-in-Time (PIT) Determinism (ADR-0033)

Every decision, backtest, and replay run uses:
- `as_of` (mandatory): the knowledge-time boundary for all facts
- `snapshot_id` (mandatory for replay, recommended for backtests): pins to a specific Alpha-Lake catalog snapshot

This ensures byte-stable reproducibility: same config + same snapshot = same decisions.

### 6.7 Pessimistic Fill Model (ADR-0009)

The fill model is shared across backtest, replay, paper, and shadow books:
- **Gap-through-stops**: if `bar.low <= stop_price`, fills at `min(open, stop_price) - slippage`
- **Gap-up entries**: cancels if the open gaps >2% above the decision quote
- **Partial fills**: scaled by `max_fill_pct` with a deterministic volume-based fill price

### 6.8 Database-Backed Halts and Run Locks (ADR-0040)

The `ops.current_halt` table stores halt state per portfolio book. Pipeline execution uses PostgreSQL advisory locks to prevent concurrent runs. The old file-based `.HALT` sentinel (ADR-0031) is being phased out. Halt transitions are recorded in `audit.halt_transition` for full traceability.

### 6.9 FastAPI Dashboard (supersedes ADR-0014)

A FastAPI + HTMX v2 SPA replaces the deprecated Streamlit dashboard. It serves 10 route modules (status, equity, positions, runs, events, quarantine, reports, journal, decisions, concepts) with SSE-based real-time updates and a DuckDB read layer for operator display.

### 6.10 Policy over Facts

Strategy modules in `domain/policy/` apply thresholds and rules to Alpha-Lake observations. Policy execution order: regime → technical → fundamental → insider → attention → earnings blackout → ranking → composite. Each policy computes a score or gate result independently.

### 6.11 Ablation Framework (ADR-0030)

Shadow books run in parallel during every pipeline execution. Each book disables one mechanism (e.g., `NO_INSIDER`, `NO_CROWDING_VETO`) to measure its marginal contribution. Books share the same Alpha-Lake decision panel — the `as_of` and `snapshot_id` are identical across all books.

### 6.12 Self-Consistency Invariants (ADR-0024)

After every pipeline run, `check_invariants` verifies: equity = cash + market value, all positions have non-negative quantity, no duplicate run IDs, and cash accounts balance. Violations trigger audit events and optionally halt the pipeline.

## 7. Runtime Flow

### Decision Run
```
1. CLI: alpha-quant run
2. Factory: create_alpha_lake_reader(config) → AlphaLakeRestClient
3. Halt check: is_halted() → ops.current_halt table (ADR-0040)
4. Store init: CanonicalStore(base_path) for legacy DuckDB state
5. Client: GET /v1/health → verify server readiness
6. Client: GET /v1/contract → verify version + capabilities
7. Client: GET /v1/observations?symbols=...&as_of=T → NeutralObservations
8. Parse: build NeutralObservations from JSON response (contracts/alpha_lake.py)
9. Assembly: build DecisionContext for each symbol (domain/decision_context.py)
10. Regime detection: regime_policy.detect(spy_ctx) → RISK_ON | CAUTION | RISK_OFF
11. Risk controls: evaluate_stops, evaluate_time_stop, evaluate_drawdown on existing positions
12. Policy: regime → technical → fundamental → insider → attention → earnings blackout → ranking → composite
13. Portfolio: size_position, fill_entry_order, mark_to_market
14. Persist (DuckDB legacy): store decisions, orders, fills, portfolio snapshot, events
15. Self-consistency: check_invariants(equity, cash, positions)
16. Persist (PostgreSQL): via OperationalStorePort → reserve_run, start_run, commit_decision_batch, book_fill, save_portfolio_mark, complete_run
17. Artifact: S3 artifact store (decision evidence JSON, SHA-256 verified)
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
[alpha_lake]
base_url = "http://alpha-lake:8000"
api_key_env = "ALPHA_LAKE_API_KEY"
mode = "rest"

[data]
mode = "live"

[bootstrap]
symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JPM"]
include_benchmarks = ["SPY", "^VIX"]

[portfolio]
max_positions = 8
max_position_pct = 0.15
risk_per_trade_pct = 0.01

[risk]
stop_atr_mult = 2.0
trail_after_r = 1.5
partial_take_at_r = 2.5
time_stop_days = 60
daily_loss_halt_pct = 0.03

[paper]
starting_equity = 100000.0
slippage_bps = 5

[llm]
provider = "openrouter"
model = "anthropic/claude-sonnet-4"

```

## 9. Related Documents

- [ADR Index](../adr/README.md)
- [C4 Architecture Diagrams](./README.md)
- [DESIGN.md](../DESIGN.md)
- [Alpha-Lake API Documentation](https://github.com/mblaauw/alpha-lake)

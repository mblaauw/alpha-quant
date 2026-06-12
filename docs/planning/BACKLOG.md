# Alpha-Quant — Implementation Backlog

> **Format:** Epic → Stories with full Acceptance Criteria and Technical Details
> **Estimation:** Story points (Fibonacci: 1, 2, 3, 5, 8)
> **Status:** 📝 Backlog · 🔍 Refining · 🏗 In Progress · ✅ Done · ❌ Blocked

---

## Epic 0: Foundation & Skeleton

**Duration:** Week 1 | **Dependencies:** None | **Size:** 13 points

Set up the project skeleton: ports, config, clock, event log, CLI scaffold, fake adapters, fixture harness, CI pipeline with golden replay. Everything downstream depends on getting these interfaces right.

---

### STORY-0.1: Project scaffold + CLI entrypoint

**Points:** 2 | **Priority:** P0 | **Status:** 📝

**Description:**
Create the `alpha_quant` Python package with directory structure per DESIGN §1, `pyproject.toml` with all dependencies, and a `cli.py` entrypoint with subcommand stubs: `run`, `replay`, `backtest`, `bootstrap`, `journal`, `ask`, `report`, `status`, `halt`.

**Acceptance Criteria:**
- [ ] `pip install -e .` installs the package
- [ ] `alpha-quant --help` shows all 9 subcommands
- [ ] Each subcommand prints a stub message and exits 0
- [ ] `ruff check .` passes with zero warnings
- [ ] `mypy --strict alpha_quant` passes (stubs can use `Any` with a TODO)
- [ ] Directory structure matches DESIGN §1 exactly:
  - `alpha_quant/domain/`, `ports/`, `data/connectors/`, `adapters/real/`, `adapters/fake/`, `app/`, `fixtures/`

**Technical Details:**
- Use `pyproject.toml` with `[project.scripts]` entry point: `alpha-quant = "alpha_quant.cli:main"`
- Dependencies (core): httpx, pydantic, pydantic-settings, structlog, sqlalchemy, duckdb, pyarrow, polars, numpy, tenacity, apscheduler, zstandard, selectolax
- Dependencies (dev): pytest, pytest-cov, hypothesis, mypy, ruff
- CLI framework: `argparse` (stdlib) — no Click/Typer dependency for v1
- Each subcommand in `alpha_quant/cli.py` dispatches to `app/` module (e.g., `app.runner`)
- Version read from `importlib.metadata` or `alpha_quant/__init__.py`

---

### STORY-0.2: Port interfaces — Clock, Store, EventSink, LLM, MarketData, Fundamentals, InsiderFeed, SentimentFeed, Broker (stub)

**Points:** 5 | **Priority:** P0 | **Status:** 📝

**Description:**
Define all port interfaces (abstract base classes or Protocols) in `alpha_quant/ports/`. These are the contracts that adapters implement and domain code depends on. The Broker port is defined but marked as NOT_IMPLEMENTED (raises `NotImplementedError` with a clear message).

**Acceptance Criteria:**
- [ ] `Clock` port: `now()`, `today()`, `market_date()` methods; nothing reads `datetime.now()` or similar anywhere in the codebase (enforced by ruff lint rule or code review)
- [ ] `MarketData` port: `daily_bars(symbol, start, end)`, `latest_quote(symbol)`, `trading_calendar(start, end)` — all return frozen pydantic models
- [ ] `Fundamentals` port: `snapshot(symbol, as_of_date)`, `earnings_calendar(start, end)`
- [ ] `InsiderFeed` port: `cluster_transactions(symbol, lookback_days)`, `recent_clusters(days)`
- [ ] `SentimentFeed` port: `mention_counts(subreddit, symbol, days)`, `baseline(symbol, window_days)`
- [ ] `Store` port: `store_bar/read_bar`, `store_decision/query_decisions`, `store_order/query_orders`, `store_fill/query_fills`, `store_position/query_positions`, `store_event/query_events`, `indicator_state(symbol)`, `update_indicator_state`
- [ ] `EventSink` port: `emit(event: DomainEvent)` where DomainEvent is a discriminated union
- [ ] `LLM` port: `explain(context: NarrationContext) → str`, `generate_card(concept: ConceptDef) → str`
- [ ] `Broker` port: `submit_order`, `cancel_order`, `positions`, `account` — all raise `NotImplementedError("Broker execution is out of scope for v1. See DESIGN §9.4.")`
- [ ] All port return types use frozen (immutable) pydantic models defined in `domain/models.py`
- [ ] All port methods are thin — no logic, just I/O contracts

**Technical Details:**
- Use `abc.ABC` + `@abstractmethod` for clarity (Protocol would also work but ABC is more explicit for a team)
- Ports never import from `adapters/` or `data/` — enforced by import linter (`ruff` rules or `import-linter` tool)
- Return types should use `Self` or concrete model types, never `dict`
- All outputs should be `@dataclass(frozen=True)` or pydantic `BaseModel` with `frozen=True` (config: `frozen=True`)
- DomainEvent is a discriminated union: `@dataclass` base class with `event_type: str` discriminator, or use Pydantic discriminated union
- `NarrationContext` is a pydantic model holding rendered numbers only — no raw data

---

### STORY-0.3: Configuration system (TOML + pydantic-settings)

**Points:** 1 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement config loading from `config.toml` using pydantic-settings with env var overrides. The config schema must match DESIGN §2 exactly.

**Acceptance Criteria:**
- [ ] `alpha-quant --config path/to/config.toml` loads custom config
- [ ] Default `config.toml` is discovered in `$PWD/config.toml` and `~/.alpha-quant/config.toml`
- [ ] Every config field is overridable via env var (e.g., `ALPHA_QUANT_PAPER__STARTING_EQUITY=50000`)
- [ ] Config model validates all numeric bounds (max_positions ≤ 20, max_position_pct ≤ 0.25, etc.)
- [ ] `alpha-quant status --config` prints full resolved config (with secrets redacted)
- [ ] Invalid config raises a clear error on startup with file + line + field name

**Technical Details:**
- Use `pydantic-settings` `BaseSettings` with `model_config = SettingsConfigDer(
            env_prefix="ALPHA_QUANT_",
            env_nested_delimiter="__",
            toml_file="config.toml"
        )`
- Sections map to nested models: `Config(BootstrapConfig, DataConfig, ...)`
- Secret fields (API keys) use `pydantic.SecretStr`
- Validation via `@field_validator` for cross-field constraints

---

### STORY-0.4: Event log system

**Points:** 2 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement the append-only typed event log. Define all event types as a discriminated union. Events are emitted by every pipeline stage and consumed by narrator/reports/dashboard.

**Acceptance Criteria:**
- [ ] All 20+ event types from DESIGN §10 are implemented as frozen dataclasses
- [ ] Events carry: `event_type`, `timestamp`, `run_id`, `payload` (type-specific), `source` (module name)
- [ ] `EventSink.emit()` writes to both SQLite (for queries) and structlog JSON stream (for debugging)
- [ ] SQLite schema: `CREATE TABLE events (id TEXT PK, run_id TEXT, event_type TEXT, ts TEXT, payload_json TEXT, source TEXT)`
- [ ] Events are queryable by `run_id`, `event_type`, date range
- [ ] `alpha-quant journal --events --since 7d` prints recent events in human-readable form
- [ ] Event emission is in the hot path — verify ≤1ms per event (benchmark test)

**Technical Details:**
- Event types as pydantic discriminated union:
  ```python
  class PipelineRunStarted(BaseEvent): event_type: Literal["PIPELINE_RUN_STARTED"] = "PIPELINE_RUN_STARTED"; run_id: str; start_ts: datetime
  class DataIngested(BaseEvent): event_type: Literal["DATA_INGESTED"]; source: str; symbol_count: int; byte_size: int
  ...
  ```
- Use `pydantic.TypeAdapter` for serialization/deserialization
- structlog integration: `structlog.get_logger().info("domain_event", event=event.model_dump_json())`
- SQLite write uses batch insert, not per-event — aggregate in a list and flush every 100ms or after each pipeline stage

---

### STORY-0.5: Clock virtualization — SystemClock + VirtualClock

**Points:** 1 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement `SystemClock` (wraps `datetime.now()` + `pandas_market_calendar` for market days) and `VirtualClock` (incrementable, allows replay across history).

**Acceptance Criteria:**
- [ ] `SystemClock.now()` returns real UTC time
- [ ] `SystemClock.today()` returns real date
- [ ] `SystemClock.market_date()` returns last trading day (using Alpaca trading calendar or fixed NYSE calendar)
- [ ] `VirtualClock` constructed with `start_date`, can be advanced by `advance(days)` or `advance_to(date)`
- [ ] `VirtualClock.market_date()` skips weekends and holidays (NYSE calendar)
- [ ] Clock is injectable — pipeline accepts a `Clock` instance at construction time
- [ ] No code outside `adapters/real/system_clock.py` and `adapters/fake/virtual_clock.py` calls `datetime.now()` — verified by `ruff` rule or grep in CI

**Technical Details:**
- For holidays, include a minimal static list: `NYSE_HOLIDAYS = [set of known dates]` — not worth a dependency
- Alternatively, accept an optional `calendar_path` in config pointing to a CSV of trading days
- `VirtualClock` stores `_current_date: date` internally, advances via `+= timedelta(days=1)`, skips non-market days
- `market_date()` is the primary method used by the pipeline; `now()` is used only for ingestion timestamps

---

### STORY-0.6: Fake adapters (all connectors)

**Points:** 2 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement fixture-backed fake adapters for every port: `FixtureMarketData`, `FixtureFundamentals`, `FixtureInsiderFeed`, `FixtureSentimentFeed`, `FixtureStore`, `CannedLLM`. These read from the fixture bundle and return deterministic, frozen data.

**Acceptance Criteria:**
- [ ] Each fake adapter implements the same port interface as its real counterpart
- [ ] `FixtureMarketData.daily_bars()` returns data from fixture parquet for the given symbol/date range
- [ ] `FixtureMarketData.latest_quote()` returns the close + estimated spread from the latest fixture bar
- [ ] `FixtureFundamentals.snapshot()` returns fixture fundamentals for the requested as-of date
- [ ] `FixtureInsiderFeed.cluster_transactions()` returns fixture insider data filtered by date range
- [ ] `FixtureSentimentFeed.mention_counts()` returns fixture mention counts for the symbol/date
- [ ] `CannedLLM.explain()` returns a deterministic template string (no real LLM call)
- [ ] Fake adapters raise clear errors when fixture data is missing (e.g., unknown symbol)
- [ ] Fake adapters never make network calls, never read OS clock

**Technical Details:**
- Fixture bundle is a directory: `fixtures/v1/` containing:
  - `bars/` — date-partitioned parquet
  - `fundamentals/` — snapshot parquet
  - `insider_tx/` — parquet
  - `mentions/` — parquet
  - `indicator_state.parquet` — pre-seeded
  - `manifest.json` — content hashes, schema versions
- `FixtureMarketData.__init__` takes path to fixture directory
- CannedLLM returns strings like: "On {date}, the system evaluated {n} candidates. {m} passed all gates. {k} new positions were opened."

---

### STORY-0.7: Bootstrap command + fixture bundle

**Points:** 3 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement `alpha-quant bootstrap` that reads the bootstrap config, fetches history for 50 symbols + benchmarks, writes raw vault → canonical → seeds indicator_state → freezes fixture bundle.

**Acceptance Criteria:**
- [ ] `alpha-quant bootstrap --symbols AAPL,MSFT,NVDA,...` processes exactly the requested symbols
- [ ] Bootstrap fetches: `history_years` of daily bars, fundamentals snapshots, earnings calendar, OpenInsider history
- [ ] Bootstrap writes to vault (zstd), then canonical (parquet + SQLite), then seeds indicator_state
- [ ] After bootstrap, `alpha-quant bootstrap --fixture-only` produces a frozen fixture bundle at `fixtures/{fixture_version}/`
- [ ] Fixture bundle includes manifest.json with content hashes for every file
- [ ] Re-running bootstrap with same config and same data is idempotent (vault skips duplicate content-addressed fetches)
- [ ] Default 50-symbol list is in config (`[bootstrap].symbols`) and includes diversity per DESIGN §3.7
- [ ] Synthetic overlays (missing-bar day, stale-feed day, mention spike) are applied on the fixture copy only

**Technical Details:**
- Content-addressed vault storage:
  ```python
  fetch_id = hashlib.sha256(f"{source}|{endpoint}|{params}|{ingest_ts}".encode()).hexdigest()[:16]
  path = vault / source / year / month / day / f"{fetch_id}.zst"
  ```
- Vault manifest is a DuckDB database: `manifest.duckdb` with table `CREATE TABLE manifest (fetch_id TEXT PK, source TEXT, endpoint TEXT, params JSON, ingest_ts TIMESTAMP, content_hash TEXT, byte_size INT)`
- Bootstrap uses real connectors for initial fetch, then freezes the fixture bundle from canonical state
- For synthetic overlays: after freezing, copy fixture bundle, then overlay modified parquet files for the synthetic cases
- Run in a transaction: if bootstrap fails mid-way, vault keeps what it has, but canonical/fixtures are in consistent state or rolled back

---

### STORY-0.8: Golden replay CI pipeline

**Points:** 1 | **Priority:** P0 | **Status:** 📝

**Description:**
Set up CI pipeline (GitHub Actions) that runs `alpha-quant replay --fixture --from 6-months-ago --to today` and asserts that the output hash matches the committed golden file.

**Acceptance Criteria:**
- [ ] GitHub Actions workflow runs on PR and push to `main`
- [ ] Workflow installs dependencies, runs `ruff check`, `mypy --strict`, `pytest`
- [ ] Golden replay: `alpha-quant replay --fixture --output golden_run.json` produces a canonical output
- [ ] CI compares golden output against `fixtures/golden/golden_run.json` via SHA256 hash
- [ ] If golden output changes intentionally, developer runs `make bless-golden` to update the committed golden file
- [ ] CI fails if hash doesn't match (prevents unintentional regressions)
- [ ] Workflow completes in <10 minutes (fixture replay itself should be <3 min)

**Technical Details:**
- Golden output file: `fixtures/golden/{fixture_version}/decision_log.json + equity_curve.json` — SHA256 of concatenated deterministic JSON
- `make bless-golden` target: runs replay, computes hash, writes to golden file
- CI matrix: Python 3.12, macOS + Ubuntu
- Use `actions/setup-python@v5` with cache for pip/uv dependencies

---

## Epic 0.5: Architecture Documentation — ADRs, C4 Diagrams & Reference Architecture Document

**Duration:** Week 1 (parallel to P0) | **Dependencies:** None (parallel) | **Size:** 25 points

Create the formal architecture documentation: 18 Architecture Decision Records (ADRs) covering every technology choice, C4 model diagrams (L1–L4) using LikeC4 DSL, and a comprehensive Reference Architecture Document (RAD) that ties together design decisions and diagrams. This runs parallel to Epic 0 — ADRs inform the scaffold and port interfaces, C4 diagrams inform the project structure.

---

### STORY-0.5.1: Write 26 ADRs covering all technology decisions

**Points:** 8 | **Priority:** P0 | **Status:** 📝

**Description:**
Write 18 Architecture Decision Records (MADR template) covering every architecturally-significant technology choice in the project. Each ADR documents the context, options considered, decision outcome, positive and negative consequences, and links to related decisions/sources.

**Acceptance Criteria:**
- [ ] 18 ADRs written to `docs/adr/` using MADR template (see `docs/planning/ADR_PLAN.md`)
- [ ] Each ADR covers Context, Decision Drivers, Considered Options (≥2), Decision Outcome, Positive/Negative Consequences
- [ ] ADR-001 through ADR-018 cover:
  - 001: Python Runtime (3.12 LTS)
  - 002: Package Manager (uv)
  - 003: Architecture Pattern (Ports-and-Adapters)
  - 004: CLI Framework (argparse stdlib)
  - 005: Configuration (pydantic-settings + TOML)
  - 006: Analytical Store (DuckDB + Parquet)
  - 007: Transactional Store (SQLite WAL + SQLAlchemy Core)
  - 008: Technical Indicators (custom numpy O(1) recurrences)
  - 009: Fill Model (custom pessimistic semantics)
  - 010: Backtesting Engine (custom event-driven)
  - 011: LLM Integration (direct httpx, no SDK)
  - 012: Primary Market Data Source (EODHD)
  - 013: Logging Strategy (structlog JSON)
  - 014: Dashboard Framework (Streamlit)
  - 015: Indicator Engine Architecture (incremental O(1))
  - 016: Data Failure Model (degrade-don't-block)
  - 017: QA Strategy (golden replay CI)
  - 018: Developer Workflow (bootstrap + fixture)
- [ ] ADRs reviewed by the team
- [ ] `docs/adr/README.md` generated with table of contents linking all 18 ADRs
- [ ] Each ADR cross-references the relevant C4 diagram(s) and RAD section(s)

**Technical Details:**
- Use MADR (Markdown ADR) template — structured sections, not freeform
- ADR directory: `docs/adr/`
- Naming: `NNNN-title-with-kebab-case.md` with zero-padded sequential numbers
- ADR statuses: all start as `Proposed`, move to `Accepted` after team review
- README.md can be auto-generated with `adr-tools` or maintained manually
- Each ADR should be 1-2 pages, focused on one decision
- Cross-references: `See C4 Container diagram (docs/architecture/views/container.png)` and `See RAD §5`

---

### STORY-0.5.2: Create C4 System Context + Container diagrams (L1–L2)

**Points:** 5 | **Priority:** P0 | **Status:** 📝

**Description:**
Create the LikeC4 DSL workspace and define Level 1 (System Context) and Level 2 (Container) C4 diagrams. These show the system's boundaries, external dependencies, and major subsystems.

**Acceptance Criteria:**
- [ ] LikeC4 DSL project initialized at `docs/architecture/` with `model.c4` entry point
- [ ] **L1 System Context** diagram shows:
  - Person: User (retail investor reading journal/dashboard)
  - Software System: Alpha-Quant (the system boundary)
  - External systems: EODHD, Alpaca Data, SEC EDGAR, OpenInsider, Reddit Public API, LLM Provider (OpenAI/OpenRouter)
  - Relationships: data flows, protocols, cadence labels
- [ ] **L2 Container** diagram shows:
  - 12 containers: CLI, Pipeline Engine, Data Layer (connectors/vault/canonical/inference/validation), Domain Core, Fill Model, Paper Portfolio, Shadow Books, LLM Narrator, Dashboard, SQLite State Store, Parquet Archive, Event Log
  - Technology labels (e.g., `[Python 3.12]`, `[httpx]`, `[DuckDB]`)
  - Relationships between containers with data flow descriptions
- [ ] Interactive preview works: `npx likec4 start` from `docs/architecture/`
- [ ] PNG exports generate: `likec4 export png -o docs/architecture/views/`
- [ ] Exported PNGs checked into repo

**Technical Details:**
- LikeC4 installation: `npx likec4` (no global install needed, runs via npm)
- DSL files: `docs/architecture/model.c4` (main model), `docs/architecture/views.c4` (view definitions)
- Element specification: define custom element kinds (`person`, `softwareSystem`, `container`, `component`)
- Use `specification` block for custom element types and styling
- Layout hints: LikeC4 auto-layouts; use relationship labels for data flow descriptions
- Technology tags on elements: `[Python 3.12]`, `[DuckDB]`, `[httpx]`
- Export command: `cd docs/architecture && npx likec4 export png -o views/`

---

### STORY-0.5.3: Create C4 Component + Dynamic diagrams (L3)

**Points:** 5 | **Priority:** P0 | **Status:** 📝

**Description:**
Define Level 3 component diagrams for the three critical subsystems (Data Layer, Decision Engine, Fill Model/Portfolio) and a Level 3 Dynamic diagram showing the daily run sequence. These decompose containers into their key components and interactions.

**Acceptance Criteria:**
- [ ] **L3 Component — Data Layer** diagram showing:
  - 5 Connectors (EODHD, Alpaca, SEC, OpenInsider, Reddit)
  - Vault (zstd, content-addressed)
  - Normalizer (pydantic parsers)
  - Canonical Writer (Parquet + SQLite writers)
  - Derive Engine (numpy indicator recurrence)
  - Validator (~15 predicate checks)
  - Catalog (dataset versioning)
- [ ] **L3 Component — Decision Engine** diagram showing:
  - M1 Universe Filter, M2 Regime Gate, M3 Technical Scorer, M4 Quality Gate, M5 Insider Scorer, M6 Crowding Veto, M7 Blackout Gate, M8 Composite Ranker
  - Position Sizer (Kelly-lite)
  - Risk Evaluator (stops, trails, drawdown, halts)
  - Data flow: filtered universe flows through gates → scores → ranking → sizing → risk
- [ ] **L3 Component — Fill Model & Portfolio** diagram showing:
  - FillEntry, FillStop, FillPartialTake, FillCorporateAction
  - PaperPortfolio (cash, positions, orders, equity)
  - 3 ShadowBooks (RULES_ONLY, NO_INSIDER, NO_CROWDING_VETO)
  - SelfConsistencyChecker
- [ ] **L3 Dynamic — Daily Run Sequence** showing step-by-step flow:
  - 17:30 ET: Ingest → Validate → Derive → Regime → Risk → Decide → Order → Persist → Narrate
  - T+1 Open: Fill queued orders → Mark equity → Self-consistency check
  - Sequence or flow-diagram layout
- [ ] All PNGs exported and checked into repo
- [ ] Interactive preview works for all views

**Technical Details:**
- Use LikeC4 `dynamic` view type for the daily run sequence diagram
- Component-level elements use `element component` kind with `component` specification
- Data flow arrows labeled with the data being passed (e.g., `list[Bar]`, `list[Candidate]`)
- For the decision engine, show the pipeline stages as sequential steps with fork/join for parallel paths

---

### STORY-0.5.4: Create C4 Deployment diagram + documentation index (L4)

**Points:** 2 | **Priority:** P1 | **Status:** 📝

**Description:**
Create the Level 4 Deployment diagram showing the physical deployment architecture, and build the documentation index that ties together ADRs, C4 diagrams, and the RAD.

**Acceptance Criteria:**
- [ ] **L4 Deployment** diagram showing:
  - Single-machine deployment (developer workstation or server)
  - APScheduler process (daily 17:30 ET cron)
  - CLI process (ad-hoc operations)
  - Streamlit process (dashboard, read-only)
  - File system: vault/ (zstd blobs), canonical/ (parquet partitions), data/state.db (SQLite)
  - Network: outbound HTTPS to 5 external APIs
- [ ] `docs/architecture/README.md` with:
  - Navigation links to all diagrams (PNG thumbnails)
  - Quick-start for viewing diagrams (`npx likec4 start`)
  - Short description of each diagram's purpose
- [ ] Architecture documentation renders and is browseable

**Technical Details:**
- Deployment diagram uses LikeC4 `deploymentNode` specification
- Show the deployment context as a single `deploymentNode` of type `"local" | "server"`
- File system elements as `infrastructure` or `storage` elements

---

### STORY-0.5.5: Write Reference Architecture Document (RAD)

**Points:** 5 | **Priority:** P0 | **Status:** 📝

**Description:**
Write the comprehensive Reference Architecture Document (`docs/architecture/REFERENCE_ARCHITECTURE.md`) that ties together the design, ADRs, and C4 diagrams into a single navigable reference. Every section references the relevant ADR(s) and C4 diagram(s).

**Acceptance Criteria:**
- [ ] RAD covers all 12 sections:
  1. Executive Summary
  2. Architectural Principles & Constraints
  3. Technology Stack Summary (18-row table referencing ADR-001–018)
  4. System Context (C4 L1) — with embedded diagram + narrative
  5. Container Architecture (C4 L2) — with embedded diagram + container descriptions
  6. Component Architecture (C4 L3) — three subsystems described with embedded diagrams
  7. Dynamic Views — daily run sequence diagram + narrative
  8. Deployment (C4 L4) — deployment diagram + description
  9. Key Architecture Decisions — ADR index table
  10. Cross-Cutting Concerns — logging, security, testing, backup
  11. Glossary — ATR, ADV, CIK, OCF, D/E, CAGR, Sharpe, Sortino, VaR
  12. References — DESIGN.md, ROADMAP.md, BACKLOG.md
- [ ] Every section references relevant ADRs (e.g., `See ADR-006` with link)
- [ ] Every section references relevant C4 diagrams (e.g., `See System Context view`)
- [ ] Cross-references are bi-directional (ADRs link back to RAD sections)
- [ ] RAD is comprehensive enough that a new team member can understand the full architecture by reading it

**Technical Details:**
- Single markdown file at `docs/architecture/REFERENCE_ARCHITECTURE.md`
- Diagrams embedded as: `![System Context](views/system-context.png)`
- ADR references: `[ADR-0006](adr/0006-use-duckdb-parquet-analytical-store.md)`
- Use anchors for intra-document navigation
- Technology stack table with columns: Layer, Technology, Version, ADR, Rationale
- RAD is a living document — updated when architecture changes

---

## Epic 1: Data Layer

**Duration:** Weeks 1–3 (overlaps with P0 after ports are defined) | **Dependencies:** P0 (ports) | **Size:** 34 points

Build the complete data subsystem: 5 connectors, raw vault, canonical stores (DuckDB parquet + SQLite), incremental indicator engine, validation gates.

---

### STORY-1.1: Shared connector machinery (base class, rate limiting, retry, vault-write)

**Points:** 3 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement the base connector infrastructure: `BaseConnector` abstract class with `httpx` client, `tenacity` retry (exponential backoff + jitter, max 5 retries), per-source token-bucket rate limiter, and automatic response-to-vault writing before any parsing.

**Acceptance Criteria:**
- [ ] `BaseConnector.__init__` creates an `httpx.Client` with configurable timeouts, user-agent, base URL
- [ ] `BaseConnector.fetch(url, params, source_name)` method:
  - Applies per-source rate limiting
  - Calls `httpx.Client.get()` with retry via `tenacity`
  - On success: writes raw bytes to vault via `vault.py` before returning parsed result
  - On failure: raises `FetchError` with source name, URL, status code
- [ ] Token-bucket rate limiter: configurable `tokens_per_second` and `max_burst`, blocks (doesn't drop) when empty
- [ ] User-Agent is set from config (mandatory for SEC compliance — must be descriptive, not generic)
- [ ] Vault write is synchronous in the fetch path (append-only, zstd-compressed)
- [ ] `stuctlog` debug log per fetch: source, URL, status, latency, byte size
- [ ] Test: rate limiter blocks when exceeded (with mocked clock), retry fires on 429/5xx, vault file is written and content-addressable

**Technical Details:**
- Rate limiter: simple leaky-bucket implementation (~30 lines of Python):
  ```python
  class TokenBucket:
      def __init__(self, rate: float, burst: int):
          self.rate = rate
          self.burst = burst
          self.tokens = burst
          self.last_refill = time.monotonic()
      def consume(self, tokens=1) -> bool:
          ...  # refill based on elapsed time, return True if tokens available
  ```
- `tenacity` decorator or `Retrying` context manager — per-connector configurable `stop=stop_after_attempt(5)`, `wait=wait_exponential(multiplier=1, min=2, max=30)`, `retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError))`
- For 429 responses specifically: retry-after header should be respected (extract and wait)
- Vault write path: `vault.store(source, endpoint, params, response_bytes, ingest_ts)` → compresses with `zstd.compress()`, computes `fetch_id`, writes file, appends to manifest

---

### STORY-1.2: EODHD connector

**Points:** 3 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement the EODHD connector for daily bars (`/eod/{sym}`), fundamentals snapshots (`/fundamentals/{sym}`), and earnings calendar (`/calendar/earnings`). This is the primary market data source.

**Acceptance Criteria:**
- [ ] `EODHDConnector.daily_bars(symbol, start, end)` returns list of `Bar` models (date, open, high, low, close, volume, adjusted_close)
- [ ] `EODHDConnector.fundamentals_snapshot(symbol)` returns `FundamentalsSnapshot` (key metrics per DESIGN M4)
- [ ] `EODHDConnector.earnings_calendar(start, end)` returns list of `EarningsDate` (symbol, report_date, fiscal_quarter)
- [ ] Batch endpoint used for EOD daily Δ: `/eod-bulk-last-day/{exchange}` for efficiently catching up all symbols
- [ ] Rate limiting per EODHD plan (default: 100k requests/day — configurable)
- [ ] Normalized response to canonical models per `normalize.py`
- [ ] All raw JSON responses go to vault before parsing
- [ ] Test: fixture file from real EODHD response parses correctly; invalid data raises `DataNormalizationError`
- [ ] Error handling: network failure → `SOURCE_DEGRADED("eodhd")` event; malformed JSON → `DataQuarantined` event

**Technical Details:**
- API base: `https://eodhd.com/api/`
- Auth: `?api_token={key}` query parameter
- Bar model: `pydantic.BaseModel` with `symbol, date, open, high, low, close, adjusted_close, volume` — all required, floats for prices
- Fundamentals: parse JSON into nested models — focus on: `OCF`, `TotalDebt`, `TotalEquity`, `Revenue`, `NetIncome`, `Accruals` (from cash flow statement)
- Earnings calendar: endpoint returns list of earnings events; if unavailable, fall back to scraping or use calculated estimates

---

### STORY-1.3: Alpaca data connector (informational only, no trading)

**Points:** 2 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement the Alpaca connector using `alpaca-py` data module only. Provides latest quotes (for spread estimation and fill realism) and trading calendar. The trading module must never be imported — enforced by lint rule.

**Acceptance Criteria:**
- [ ] `AlpacaDataConnector.latest_quote(symbol)` returns `Quote` model (bid, ask, bid_size, ask_size, timestamp)
- [ ] `AlpacaDataConnector.trading_calendar(start, end)` returns list of market dates
- [ ] `AlpacaDataConnector.latest_bar(symbol)` returns latest `Bar` (used for position marking)
- [ ] Uses `alpaca-py` `StockHistoricalDataClient` only — no `TradingClient`
- [ ] Import lint rule: `from alpaca.trading` or similar in any file fails CI
- [ ] Rate limiting per Alpaca plan (free tier: IEX data, 200 req/min)
- [ ] Key/secret from config, never hardcoded
- [ ] Test: mock `StockHistoricalDataClient` responses → verify parsing; fixture quote file parses correctly
- [ ] When Alpaca is unreachable: `SOURCE_DEGRADED("alpaca")` event, spread model falls back to fixed 10 bps

**Technical Details:**
- Import only: `from alpaca.data.historical import StockHistoricalDataClient`
- `StockHistoricalDataClient.get_stock_quotes(symbol_or_symbols, ...)` → returns `Quote` objects
- `StockHistoricalDataClient.get_trading_calendar(start, end)` → returns list of trading dates
- Spread estimate: `(ask - bid) / mid` if bid/ask valid, else default 0.001 (10 bps)
- Lint rule: add `"TCH001"` or custom ruff rule — simplest approach: add a grep to CI: `! grep -r "alpaca\.trading" alpha_quant/`

---

### STORY-1.4: SEC ticker map connector

**Points:** 1 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement the SEC connector to fetch and parse `company_tickers.json`. Provides the authoritative ticker → CIK → exchange mapping for universe validation.

**Acceptance Criteria:**
- [ ] `SECConnector.ticker_map()` returns `dict[str, TickerRecord]` where `TickerRecord` has: `ticker, cik, name, exchange, sic_code`
- [ ] Fetches from `https://www.sec.gov/files/company_tickers.json` with compliant User-Agent (must be descriptive, include contact info)
- [ ] User-Agent is configurable in config.toml under `[sec].user_agent`
- [ ] Rate limit: max 1 request per second (SEC fair access policy)
- [ ] Caches to SQLite with timestamp: re-fetches weekly (configurable)
- [ ] On failure: uses last-good cache, emits `SOURCE_DEGRADED("sec")` event
- [ ] Test: fixture file from real SEC response parses; empty/malformed response raises clear error

**Technical Details:**
- SEC `company_tickers.json` format: `{"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}`
- Parse into structured model, index by ticker
- CIK is zero-padded to 10 digits for SEC EDGAR lookups
- User-Agent format: `"CompanyName (contact@example.com)"` — **mandatory**, SEC blocks generic UAs
- Weekly refresh via `alpha-quant bootstrap --refresh-sec` or automatic in daily run on the correct day

---

### STORY-1.5: OpenInsider connector

**Points:** 3 | **Priority:** P1 | **Status:** 📝

**Description:**
Implement the OpenInsider connector to scrape insider transaction cluster data. Provides the data backing for M5 (insider cluster signal).

**Acceptance Criteria:**
- [ ] `OpenInsiderConnector.recent_clusters(days=30)` returns list of `InsiderCluster` (symbol, avg_price, total_shares, total_value, transaction_type, officer_count, director_count, max_date)
- [ ] `OpenInsiderConnector.cluster_for_symbol(symbol, days=30)` returns single `InsiderCluster` or None
- [ ] Parses HTML from `http://openinsider.com/` screener pages (latest cluster buys, by-date)
- [ ] Rate limit: 1 request per 3 seconds (be polite), configurable burst
- [ ] Cache aggressively: same-day responses are served from vault, not re-fetched
- [ ] HTML parsing with `selectolax` (fast CSS selector parser) — fallback to `lxml` if selectolax unavailable
- [ ] Test: fixture HTML file parses correctly; malformed HTML raises `DataNormalizationError`
- [ ] On failure: `SOURCE_DEGRADED("openinsider")` → M5 returns neutral (no boost)

**Technical Details:**
- Target page: `http://openinsider.com/screener?s=&o=&pl=&ph=&ll=&lh=&fd=0&fdr=&td=0&tdr=&fdlyl=&fdlyh=&daysago=&transaction_type=&transaction_start_date=&transaction_end_date=&company_id=&maxrows=100&x=1`
- Parse table rows: extract `Ticker`, `Company`, `Insider Name`, `Title`, `Transaction Type`, `Price`, `Qty`, `Value`, `Date`
- Cluster detection: group by symbol within a window, count unique officers/directors, sum value
- M5 eligibility: ≥2 distinct officers/directors, ≥$200k net transaction value (buys minus sells) in 30 days
- HTML structure changes frequently — add a test that alerts on structural changes (compare known-good parse, flag if row count differs massively)

---

### STORY-1.6: Reddit public sentiment connector

**Points:** 2 | **Priority:** P1 | **Status:** 📝

**Description:**
Implement the Reddit connector using public JSON endpoints. Provides mention counts for M6 (crowding veto). No API key needed, no OAuth — public endpoints only.

**Acceptance Criteria:**
- [ ] `RedditConnector.mention_counts(symbol, days=30, subreddits=["wallstreetbets","stocks"])` returns `MentionCounts` (symbol, date, count_wsb, count_stocks, total)
- [ ] `RedditConnector.baseline(symbol, window_days=30)` returns `MentionBaseline` (mean, std, z_score)
- [ ] Fetches from `https://www.reddit.com/r/{sub}/new.json` — looks for symbol mentions in post titles
- [ ] Rate limit: 10 requests per minute (unauthenticated), configurable
- [ ] User-Agent required per Reddit policy
- [ ] Case-insensitive ticker matching, filters out common words (e.g., "DD" for due diligence, "RH" for RH stock)
- [ ] Count arithmetic only — no LLM sentiment analysis
- [ ] Test: fixture JSON from Reddit API parses; filtered ticker list returns correct counts
- [ ] On failure: `SOURCE_DEGRADED("reddit")` → M6 fails open with raised entry bar

**Technical Details:**
- URL format: `https://www.reddit.com/r/wallstreetbets/new.json?limit=100`
- Parse JSON response: iterate `data.children[].data`, check `title` for ticker matches
- Use regex `\b(AAPL|MSFT|...)\b` — build pattern dynamically from universe symbols
- Common-word filter list: `["DD", "RH", "IT", "GO", "EV", "AI", "YT", "UK", "US", "CEO", "CFO", "ETF", "IPO", "PE", "EPS"]`
- 30-day rolling baseline: store daily counts in SQLite, compute z-score = `(current - mean) / std`
- z > 3 → M6 veto (10-day entry block for that symbol)

---

### STORY-1.7: Raw vault implementation

**Points:** 2 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement `vault.py`: the append-only, content-addressed, zstd-compressed raw payload archive. Nothing in the vault is ever deleted or rewritten.

**Acceptance Criteria:**
- [ ] `Vault.store(source, endpoint, params, data_bytes, ingest_ts)` writes compressed blob to `vault/{source}/{yyyy}/{mm}/{dd}/{fetch_id}.zst`
- [ ] `Vault.read(fetch_id)` returns the decompressed bytes
- [ ] `Vault.read_manifest(source, start_date, end_date)` returns list of manifest entries for replay
- [ ] `Vault.dates_for_source(source)` returns set of dates with data
- [ ] Vault root path is configurable (default: `data/vault/`)
- [ ] Zstd compression level configurable (default: 3)
- [ ] Manifest is a DuckDB database (`manifest.duckdb`) with: `fetch_id, source, endpoint, params (JSON), ingest_ts (TIMESTAMP), content_hash (TEXT), byte_size (INT)`
- [ ] Concurrent writes are safe (DuckDB handles single-writer; use WAL mode)
- [ ] Test: read back written data matches original; duplicate content-addressable fetch_id raises stored-but-skipped (not error); manifest queries work

**Technical Details:**
- `fetch_id = sha256(f"{source}|{endpoint}|{json_params}|{ingest_ts.isoformat()}".encode())[:16].hex()` — 16 hex chars (64-bit collision resistance is enough for this scale)
- Zstd: `import zstandard as zstd; compressor = zstd.ZstdCompressor(level=3); compressed = compressor.compress(data_bytes)`
- DuckDB manifest: attach database at vault init; `CREATE TABLE IF NOT EXISTS manifest (...)`
- Write path: check manifest for existing `fetch_id` → skip if exists (idempotent), else write blob + insert manifest row

---

### STORY-1.8: Normalization (pydantic models + parsers)

**Points:** 3 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement `normalize.py` with pydantic models and parser functions that convert raw HTTP response bytes into structured canonical models. This is the "parse, don't validate" boundary.

**Acceptance Criteria:**
- [ ] `normalize_eodhd_bars(raw_json: bytes) → list[Bar]` — handles single and batch responses
- [ ] `normalize_eodhd_fundamentals(raw_json: bytes) → FundamentalsSnapshot`
- [ ] `normalize_alpaca_quote(raw: bytes) → Quote`
- [ ] `normalize_sec_tickers(raw_json: bytes) → dict[str, TickerRecord]`
- [ ] `normalize_openinsider_html(raw_html: bytes) → list[InsiderTransaction]`
- [ ] `normalize_reddit_mentions(raw_json: bytes) → list[Mention]`
- [ ] All normalization is a pure function: `raw_bytes → Optional[CanonicalModel]`
- [ ] Invalid/malformed data returns `None` and emits log warning, not exception
- [ ] Test: fixture raw responses for each source produce expected models; edge cases (missing fields, wrong types) handled gracefully
- [ ] All canonical models are frozen pydantic BaseModels with type validation

**Technical Details:**
- Bar model: `symbol: str, date: date, open: float, high: float, low: float, close: float, volume: int, adjusted_close: float`
- FundamentalsSnapshot: `symbol: str, snapshot_date: date, operating_cash_flow: Optional[float], total_debt: Optional[float], total_equity: Optional[float], revenue: Optional[float], net_income: Optional[float], accruals: Optional[float]` (+ more as needed for M4)
- InsiderTransaction: `symbol: str, filed_date: date, transaction_date: date, insider_name: str, title: str, transaction_type: Literal["Buy","Sale"], shares: int, price: float, value: float, is_direct: bool`
- Mention: `symbol: str, date: date, subreddit: str, count: int`
- Use `pydantic.TypeAdapter` for parsing JSON with nested models
- For OpenInsider HTML: use selectolax CSS selectors, extract table rows, map to InsiderTransaction

---

### STORY-1.9: Canonical store — Parquet/DuckDB for analytical data + SQLite for transactional state

**Points:** 5 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement the canonical store layer. Analytical data (bars, fundamentals, insider, mentions) → date-partitioned Parquet queried via DuckDB. Transactional data (decisions, orders, fills, positions, events, indicator state) → SQLite WAL.

**Acceptance Criteria:**
- [ ] `CanonicalStore.write_bars(bars: list[Bar])` appends to `canonical/bars/date={date}/part.parquet`
- [ ] `CanonicalStore.read_bars(symbol, start, end)` returns polars DataFrame or list[Bar]
- [ ] `CanonicalStore.write_fundamentals(snapshots)` writes to `canonical/fundamentals/snapshot_date={date}/`
- [ ] `CanonicalStore.write_insider_transactions(txns)` writes to `canonical/insider_tx/filed_date={date}/`
- [ ] `CanonicalStore.write_mentions(mentions)` writes to `canonical/mentions/date={date}/`
- [ ] SQLite store: `StateStore.create_tables()` creates schema: `decisions`, `orders`, `fills`, `positions`, `equity_curve`, `events`, `concept_log`, `indicator_state`, `catalog`
- [ ] `StateStore.write_decision(decision)` inserts into `decisions` table
- [ ] `StateStore.read_positions(as_of_date)` returns current positions
- [ ] `StateStore.read_indicator_state(symbol)` returns current indicator values or None
- [ ] `StateStore.update_indicator_state(symbol, state)` upserts
- [ ] All writes are transactional (SQLite WAL mode, batch commits)
- [ ] Test: double-ingest produces zero new canonical rows (idempotency); DuckDB query over parquet returns correct date range
- [ ] 50-day tail prune: `CanonicalStore.prune_bars(before_date)` removes date partitions older than the tail window

**Technical Details:**
- Parquet writing with pyarrow:
  ```python
  import pyarrow as pa
  import pyarrow.parquet as pq
  table = pa.Table.from_pydict(bars_to_dict(bars))
  path = f"canonical/bars/date={date}/part.parquet"
  pq.write_table(table, path, compression="zstd")
  ```
- DuckDB query: `duckdb.sql("SELECT * FROM read_parquet('canonical/bars/**/*.parquet', hive_partitioning=true) WHERE symbol = ? AND date BETWEEN ? AND ?", [symbol, start, end])`
- SQLite schema (SQLAlchemy Core):
  ```sql
  CREATE TABLE decisions (
      decision_id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL,
      date DATE NOT NULL,
      symbol TEXT NOT NULL,
      action TEXT NOT NULL,  -- "ENTER", "EXIT", "HOLD"
      score REAL,
      mechanism_results JSON,  -- all M1-M8 results
      created_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  )
  ```
- Positions: `position_id, symbol, entry_date, entry_price, current_shares, stop_price, trail_activated, partial_taken, sector, decision_id FK`
- Indicator state: `symbol TEXT PK, ema20 REAL, ema50 REAL, ..., last_date DATE, updated_ts TIMESTAMP`
- Prune: DuckDB `SELECT DISTINCT date FROM read_parquet(...)` → drop directories outside tail window via `shutil.rmtree`

---

### STORY-1.10: Incremental indicator engine (numpy, O(1) recurrence)

**Points:** 3 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement `derive.py`: incremental O(1) calculation of technical indicators using numpy recurrence formulas. No pandas-ta or TA-Lib — all Wilder/EMA recurrences in ~100 lines of numpy.

**Acceptance Criteria:**
- [ ] `update_indicator_state(state, new_bar) → IndicatorState` updates:
  - EMA(20), EMA(50), EMA(200) via: `ema = price * α + prev_ema * (1 - α)`
  - RSI(14) via Wilder smoothing: `avg_gain = prev_avg_gain * 13/14 + gain * 1/14`
  - ATR(14) via: `atr = prev_atr * 13/14 + tr * 1/14`
  - MACD line, signal line, histogram from EMA12 and EMA26
- [ ] All updates are O(1) — no window recomputation
- [ ] `backfill_indicator_state(symbol, bars: list[Bar]) → IndicatorState` seeds state from full history (cold start)
- [ ] `backfill_month_end_closes(bars) → list[tuple[date, float]]` extracts month-end closes for 12-1 momentum
- [ ] Integrity test: recompute from full 250-day window via brute-force and compare to incremental state — must match to 1e-6
- [ ] Performance: 10,000 symbols × 1 update takes <10ms
- [ ] State is serializable/deserializable via pydantic for SQLite storage

**Technical Details:**
- All numpy, no loops:
  ```python
  alpha_ema = 2 / (period + 1)
  new_ema = price * alpha_ema + prev_ema * (1 - alpha_ema)
  ```
- RSI Wilder:
  ```python
  gain = max(current_close - prev_close, 0)
  loss = max(prev_close - current_close, 0)
  avg_gain = prev_avg_gain * 13/14 + gain * 1/14
  avg_loss = prev_avg_loss * 13/14 + loss * 1/14
  rsi = 100 - 100 / (1 + avg_gain / max(avg_loss, 1e-10))
  ```
- True Range: `max(high - low, abs(high - prev_close), abs(low - prev_close))`
- MACD: EMA12 - EMA26, then EMA9 of that for signal line
- 12-1 momentum: `(close_12mo_ago - close_1mo_ago) / close_1mo_ago` — use month-end closes
- IndicatorState model:
  ```python
  class IndicatorState(BaseModel, frozen=True):
      symbol: str
      ema20: float; ema50: float; ema200: float
      rsi_avg_gain: float; rsi_avg_loss: float; rsi: float
      atr: float
      macd_line: float; macd_signal: float; macd_histogram: float
      last_close: float; last_date: date
  ```

---

### STORY-1.11: Validation gates

**Points:** 2 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement `validate.py` with declarative quality checks between every data zone. ~15 predicate functions that emit `DataQuarantined` or `StalenessHaltSet` events.

**Acceptance Criteria:**
- [ ] `validate_bar(bars: list[Bar]) → list[ValidationResult]` checks:
  - No zero/negative prices
  - No single-day |return| > 40% without corporate action record → quarantined
  - No missing dates in expected trading calendar (gaps > 1 market day → quarantined)
  - No NaN/Inf values
  - Volume > 0
- [ ] `validate_fundamentals(snapshot) → ValidationResult` — schema drift (extra/missing fields) → quarantined
- [ ] `validate_staleness(last_update_ts, threshold_hours) → Optional[StalenessHaltSet]` — if last update > threshold → halt
- [ ] `validate_indicator_state(state) → ValidationResult` — NaN in any field → quarantined
- [ ] Quarantined symbol: excluded from universe (M1) until manually cleared or next bootstrap
- [ ] Halt: `DATA_HALT` event → pipeline stops, `alpha-quant status` shows HALTED
- [ ] Test: fixture with bad data (zero price, gap day) triggers correct quarantine; stale feed triggers halt
- [ ] All validators are pure functions: `(data) → list[ValidationResult]`

**Technical Details:**
- `ValidationResult`: `typing.TypedDict` or frozen dataclass with `is_valid: bool, issues: list[Issue], severity: Literal["WARN","QUARANTINE","HALT"]`
- Quarantine list stored in SQLite: `quarantine: symbol TEXT, reason TEXT, date DATE, cleared BOOLEAN`
- Halt mechanism: symlink or lockfile at `data/.HALT` with reason + timestamp; pipeline checks this before every run
- No rules engine — each check is a standalone function with a name like `check_negative_prices(bars)`, `check_date_gaps(dates, calendar)`, etc.
- ~15 checks total, easy to add more as predicates

---

### STORY-1.12: Catalog + dataset versioning

**Points:** 1 | **Priority:** P1 | **Status:** 📝

**Description:**
Implement `catalog.py` for dataset versioning, manifest tracking, and fixture integrity verification. Ensures reproducibility across runs and environments.

**Acceptance Criteria:**
- [ ] `Catalog.register_run(run_type, config_hash, fixture_version)` stores run metadata
- [ ] `Catalog.compute_dataset_hash(path)` returns SHA256 of concatenated file contents
- [ ] `Catalog.verify_fixture_integrity(fixture_path, manifest)` checks file content hashes match
- [ ] `Catalog.current_fixture_version()` reads from SQLite state store
- [ ] `Catalog.list_runs(since_date)` returns list of runs with type, date, config hash
- [ ] Golden replay uses catalog to verify hash matches committed golden file
- [ ] Test: fixture tampering (modify one parquet file) causes integrity check failure

**Technical Details:**
- Catalog table in SQLite: `run_id TEXT PK, run_type TEXT, config_hash TEXT, fixture_version TEXT, start_ts TIMESTAMP, end_ts TIMESTAMP, status TEXT`
- Manifest verification: read manifest JSON, iterate files, compare SHA256, report mismatches
- Dataset hash for golden comparison: sort files by path, concatenate content bytes, SHA256

---

## Epic 2: Domain + Backtest + Paper Engine

**Duration:** Weeks 3–5 | **Dependencies:** P0, P1 | **Size:** 40 points

Build the core decision engine (M1–M4, M7, M8), position sizing, risk management, fill model, backtester, paper portfolio engine, and shadow ablation books.

---

### STORY-2.1: Domain models (Candidates, Positions, Orders, Decisions)

**Points:** 2 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement all frozen domain models in `domain/models.py`. These are the shared vocabulary across the entire system — no dicts, no tuples, always typed models.

**Acceptance Criteria:**
- [ ] `Candidate` model: `symbol, date, score_technical, score_momentum, score_insider, composite_score, regime, passes_m1, passes_m4, passes_m6, passes_m7, block_reason: Optional[str]`
- [ ] `Position` model: `symbol, entry_date, entry_price, current_price, shares, cost_basis, stop_price, trail_price, trail_activated: bool, partial_taken: bool, atr_at_entry, sector, decision_id`
- [ ] `Order` model: `order_id, symbol, action (ENTER/EXIT/PARTIAL), order_type (MARKET/LIMIT), limit_price: Optional[float], quantity, decision_id, status (PENDING/FILLED/CANCELLED/REJECTED), created_date, fill_date: Optional[date]`
- [ ] `Decision` model: `decision_id, run_id, date, symbol, action, candidate: Optional[Candidate], position: Optional[Position], order: Optional[Order], risk_check_results: dict, mechanism_results: dict`
- [ ] All models are `pydantic.BaseModel` with `model_config = ConfigDict(frozen=True)`
- [ ] Models use `field_validator` for cross-field consistency (e.g., `partial_taken` implies `trail_activated`)
- [ ] All dates are `datetime.date` (not `str` or `datetime.datetime`)
- [ ] All monetary values are `float` (not `Decimal` — simplicity over precision for paper trading)

**Technical Details:**
- Keep models focused on data, zero behavior
- No methods beyond `model_dump()` and `model_validate()` (inherited from pydantic)
- Use `Optional[X] = None` for fields that aren't always present
- Sector is a `str` — lookup from a static sector map file (`data/sectors.csv` from EODHD or manual mapping)

---

### STORY-2.2: Universe selection (M1)

**Points:** 2 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement M1 universe selection: filter the symbol universe by liquidity, price, and SEC-map validity. Produces the list of tradeable candidates for further scoring.

**Acceptance Criteria:**
- [ ] `M1Universe.select(date, all_symbols, market_data, fundamentals) → list[UniverseMember]` returns symbols passing:
  - Price ≥ `min_price` (config, default $5.0)
  - Average daily volume ≥ `min_adv_usd` (config, default $5M)
  - SEC map has valid CIK
  - Not in quarantine list
  - Has recent price data (within `staleness_halt_hours`)
- [ ] Returns `UniverseMember(symbol, price, volume_adv, market_cap, sector, passes_m1, fail_reason: Optional[str])`
- [ ] Performance: 5000 symbols in <50ms
- [ ] Test: symbol below $5 is excluded; low-volume symbol is excluded; quarantined symbol is excluded

**Technical Details:**
- ADV calculation: median of daily dollar volume over trailing 20 trading days
- SEC map lookup: cache of `{ticker: TickerRecord}` loaded at pipeline start
- Quarantine list: read from SQLite `quarantine` table where `cleared = FALSE`
- Output is used by M3, M4, M5 — all other mechanisms receive this filtered list

---

### STORY-2.3: Regime detection (M2)

**Points:** 3 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement M2 regime gate: classify current market environment as `RISK_ON`, `CAUTION`, or `RISK_OFF` based on SPY trend, market breadth, and VIX level.

**Acceptance Criteria:**
- [ ] `M2Regime.detect(spy_bars: list[Bar], spy_indicator: IndicatorState, vix_level: float, breadth_data) → Regime`
- [ ] Regime is `Literal["RISK_ON", "CAUTION", "RISK_OFF"]`
- [ ] Logic per DESIGN §5:
  - SPY price > EMA50 > EMA200 AND VIX < 20 AND breadth > 0.4 → RISK_ON
  - SPY price < EMA200 OR VIX > 30 → RISK_OFF
  - Everything else → CAUTION
- [ ] Breadth: percentage of SP500 stocks above their 50-day SMA
- [ ] On RISK_OFF: no new entries, reduce position size multiplier to 0
- [ ] On CAUTION: position size multiplier 0.5
- [ ] On RISK_ON: position size multiplier 1.0
- [ ] `RegimeChanged` event emitted when regime switches
- [ ] Test: SPY bull market fixture → RISK_ON; SPY bear market fixture → RISK_OFF; borderline → CAUTION

**Technical Details:**
- Breadth: requires calculating SMA50 for all SP500 members — this can be approximated from the universe data
- VIX level: from configured VIX symbol (^VIX in config, or a VIX ETF like VIXY)
- Simple ladder, not a model — no ML, no hidden states
- Regime state stored in SQLite: `current_regime TEXT, as_of_date DATE, spy_price REAL, vix_level REAL`
- Position sizing multiplier is read from this state by `sizing.py`

---

### STORY-2.4: Technical score (M3)

**Points:** 3 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement M3 technical scoring: composite score from trend, momentum, RSI zone, MACD, volume confirmation, and ATR sanity.

**Acceptance Criteria:**
- [ ] `M3TechnicalScore.score(symbol, bars: list[Bar], indicator: IndicatorState) → TechnicalScore`
- [ ] Sub-components (each 0.0–1.0):
  - Trend: `price / EMA50` ratio (linear map: 0.95→0.0, 1.05→1.0, clamp)
  - Momentum: 12-1 month return (linear map: -0.1→0.0, 0.15→1.0)
  - RSI zone: RSI 45–55 = 0.75, 55–65 = 1.0, 65–70 = 0.5, <45 or >70 = 0.0
  - MACD histogram: positive = 1.0, negative = 0.0 (current vs prior bar)
  - Volume confirmation: current volume > 20-day avg = 1.0, else 0.5
  - ATR sanity: ATR / price < 0.05 = 1.0, 0.05–0.08 = 0.5, >0.08 = 0.0
- [ ] Composite: weighted average of sub-components (weights in config or hardcoded per DESIGN)
- [ ] Score is 0.0–1.0, used in M8 composite ranking
- [ ] Test: bull flag fixture → high score; declining stock → low score; low volatility → passes ATR sanity

**Technical Details:**
- All inputs come from `IndicatorState` (incremental) and raw bars (for volume avg)
- No lookahead: use only data available as of the evaluation date
- Momentum formula: `(close_12mo_ago - close_1mo_ago) / close_1mo_ago` — from month-end closes in derived state
- Trend: simple ratio, not regression — fast and effective

---

### STORY-2.5: Fundamental quality gate (M4)

**Points:** 2 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement M4 fundamental quality gate: binary pass/fail based on operating cash flow, debt/equity, accruals, and earnings surprise.

**Acceptance Criteria:**
- [ ] `M4QualityGate.evaluate(symbol, fundamentals: FundamentalsSnapshot) → QualityVerdict`
- [ ] Verdict: `{"pass": bool, "reason": Optional[str]}`
- [ ] Checks:
  - Positive operating cash flow (OCF > 0)
  - Debt/Equity < sector median * 2 (sector-relative)
  - No recent negative earnings surprise (last 2 quarters beat or ≤ -5% miss)
  - Accruals ratio (accruals / avg_assets) within [-0.05, 0.05]
- [ ] If fundamentals data is missing (not yet ingested) → pass with `SOURCE_DEGRADED` event (fail-open)
- [ ] Test: company with negative OCF → fail; healthy company → pass; missing fundamentals → pass with degraded event

**Technical Details:**
- Accruals calculation: `(Net Income - Operating Cash Flow) / Average Total Assets`
  - Net income and OCF from income/cash flow statements via EODHD fundamentals
  - If cash flow statement not available, use balance sheet approach or fall through
- Sector median D/E: compute per sector from the universe; stored in SQLite and recalculated weekly
- Earnings surprise: compare actual EPS to estimated EPS from earnings calendar
- If any fundamental field is unavailable, log a specific warning and pass through (fail-open for the gate)

---

### STORY-2.6: Earnings blackout (M7)

**Points:** 1 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement M7 earnings blackout: block new entries for symbols within 3 trading days before their earnings report.

**Acceptance Criteria:**
- [ ] `M7EarningsBlackout.check(symbol, date, earnings_calendar) → BlackoutVerdict` — pass/fail with reason
- [ ] Blackout window: 3 trading days before earnings report date
- [ ] Uses earnings calendar from EODHD (stored in SQLite)
- [ ] If earnings date unknown (not in calendar) → pass (no blackout for unknown)
- [ ] Test: 2 days before earnings → blocked; 4 days before → allowed; day after earnings → allowed

**Technical Details:**
- Earnings calendar table: `symbol, report_date, fiscal_quarter, estimated_eps, actual_eps`
- Blackout window: `[report_date - 3 trading days, report_date - 1 trading day]`
- Trading days: use the same market calendar from Clock port

---

### STORY-2.7: Composite ranking (M8)

**Points:** 1 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement M8 composite ranking: combine M3 and M5 scores with weights, apply all gates (M1, M4, M6, M7), rank candidates, and produce the ordered list for position entry.

**Acceptance Criteria:**
- [ ] `M8CompositeRanker.rank(candidates: list[Candidate], regime, current_positions) → list[RankedCandidate]`
- [ ] Weight formula: `composite = 0.6 * technical_score + 0.25 * momentum_score + 0.15 * insider_boost`
- [ ] Gates applied first: any candidate failing M1, M4, M6, or M7 is excluded with reason
- [ ] Insider boost (M5): if insider cluster detected, add the weighted contribution; if no data, score from M3+M4 only
- [ ] Ties broken by liquidity (higher ADV first)
- [ ] Only candidates scoring > 0.5 are considered for entry
- [ ] Returns ranked list, top N = `max_positions - current_positions` (DESIGN §6)
- [ ] Test: candidate with insider cluster ranks higher than equal-technical competitor; gated candidates excluded; liquidity tiebreak works

**Technical Details:**
- Insider boost: if M5 passes, multiply: `insider_score = 0.15` (full weight); else `insider_score = 0.0`, and the 0.15 redistributes: 0.70 technical + 0.30 momentum
- Rankings computed after gates: gates are hard filters, not soft scores
- Output is consumed by the ordering process in `app/pipeline.py`

---

### STORY-2.8: Position sizing (Kelly-lite + risk parity)

**Points:** 2 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement position sizing: `shares = (equity * risk_per_trade) / (2 * ATR)`, with position, sector, and gross exposure caps, multiplied by regime and drawdown factors.

**Acceptance Criteria:**
- [ ] `size_position(equity, price, atr, regime_multiplier, dd_multiplier, config) → PositionSize`
- [ ] Base formula: `notional = (equity * risk_per_trade_pct) / (2 * atr / price)` — risk-normalized
- [ ] Caps applied in order:
  1. Per-position max: `notional = min(notional, equity * max_position_pct)`
  2. Gross exposure: total notional ≤ `equity * max_gross_exposure`
  3. Per-sector: ≤ `max_sector_positions` in same sector
  4. Regime multiplier: `× 1.0 (RISK_ON), × 0.5 (CAUTION), × 0.0 (RISK_OFF)`
  5. Drawdown multiplier: `× 1.0 (DD < 10%), × 0.5 (10% ≤ DD < 15%), × 0.0 (DD ≥ 15%)`
- [ ] Returns: `PositionSize(symbol, shares: int, notional: float, risk_at_stop: float, capped_by: list[str])`
- [ ] Test: sizing at exactly the cap limits; regime RISK_OFF → zero shares; DD ladder reduction

**Technical Details:**
- `shares = int(notional / price)` — round down to whole shares (fractional shares not supported in v1)
- `risk_at_stop = shares * stop_distance * price` — verify this ≤ 2% equity (I5)
- `capped_by` list enables debugging: `["max_position_pct", "gross_exposure"]`
- The function is pure — all inputs (equity, atr, price, etc.) are passed as arguments

---

### STORY-2.9: Risk management — stops, trails, takes, drawdown, halts

**Points:** 3 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement risk.py: all risk rule evaluation. Structurally exit-only — this module can only reduce or close positions. Never initiates entries.

**Acceptance Criteria:**
- [ ] `evaluate_stops(position, current_bar, config) → list[RiskAction]`:
  - 2×ATR initial stop: new stop = `entry_price - 2 * atr_at_entry`
  - Trail after +1R: if `high > entry_price + 1 * atr_at_entry`, trail activates
  - Trailing stop: trail price = `highest_since_entry - 2 * atr_at_entry`
  - Partial take at +2R: if `high > entry_price + 2 * atr_at_entry`, sell 50%
- [ ] `evaluate_time_stop(position, current_date, config)` → close if held > `time_stop_days`
- [ ] `evaluate_drawdown(equity_curve, config)` → `(dd_pct: float, dd_mult: float, action: Optional[str])`
- [ ] `evaluate_daily_loss(daily_pnl, equity, config)` → halt if loss > `daily_loss_halt_pct` of equity
- [ ] `evaluate_all(positions, current_bar, equity_curve, config) → list[RiskAction]`
- [ ] `RiskAction`: `{"type": Literal["STOP", "TRAIL", "PARTIAL_TAKE", "TIME_STOP", "DRAWDOWN_REDUCE", "DAILY_LOSS_HALT"], "position_id": str, "shares": int, "reason": str, "price_estimate": float}`
- [ ] Test: stop touched by intraday low → exit; trail activated after 1R; partial take fires at 2R; 30-day hold → time stop; DD ladder reduces; daily loss halts

**Technical Details:**
- Stop evaluation against daily bar: `if bar.low <= stop_price → exit at min(bar.open, stop_price) - slippage`
  - This happens in the fill model (§9.2), but the risk module decides *what* stops/trails are active
- `highest_since_entry` tracked in Position model field `highest_price` or computed from bars since entry
- Drawdown: compute peak-to-trough from equity curve points; store `peak_equity, current_dd_pct` in SQLite
- All risk actions are idempotent: if a stop already triggered, don't re-trigger
- The function returns actions, does not execute them — execution happens in `app/pipeline.py`

---

### STORY-2.10: Fill model — THE model (backtest, replay, paper, shadows)

**Points:** 5 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement `domain/fills.py`: THE fill model used identically by backtest, replay, paper, and shadow books. One function, five consumers. Conservative semantics (gap-through-stop fills at open, not stop).

**Acceptance Criteria:**
- [ ] `fill_entry_order(order, entry_bar, latest_quote, config) → FillResult`:
  - Fill price = `entry_bar.open + slippage_bps + half_spread_estimate`
  - If `abs(entry_bar.open / order.decision_quote - 1) > 0.002` → order cancels (gap too large)
  - Returns: `FillResult(order_id, fill_price, shares, fill_date, cancelled: bool, cancel_reason: Optional[str])`
- [ ] `fill_stop_order(position, stop_price, bar, config) → FillResult`:
  - If `bar.low <= stop_price` → fill at `min(bar.open, stop_price) - slippage`
  - Gap-down case: fill at `bar.open - slippage` (pessimistic)
- [ ] `fill_partial_take(position, take_price, bar, config) → FillResult`:
  - If `bar.high >= take_price` → fill at `max(bar.open, take_price) + slippage` (sell)
  - Sell 50% of current position shares
- [ ] `apply_corporate_action(position, corporate_action) → Position`:
  - Cash dividend: add `shares * dividend_amount` to cash
  - Stock split: adjust `shares` and `entry_price`, `stop_price` proportionally
- [ ] Idempotency: `fill_id = sha256(decision_id | fill_date)`; re-running same day produces same fills
- [ ] Test: gap-through-stop → fills at open, not stop; normal stop → fills at stop; gap-up entry → order cancels; partial take → 50% filled; dividend → cash added; split → adjusted
- [ ] Performance: 1000 fills in <100ms

**Technical Details:**
- Slippage model: `slippage_bps` from config (default 5) + `half_spread_estimate` from latest Alpaca quote
- Half-spread: `(ask - bid) / (2 * mid)` if valid, else `0.001` (10 bps fallback)
- Fill determinism: store `(decision_id, fill_date)` → hash → `fill_id`; on re-run, look up existing fills by hash
- Corporate action data: from EODHD fundamentals or Alpaca corporate actions endpoint
- FillResult: frozen pydantic model with `order_id, fill_id, fill_price, shares, fill_date, cancelled, cancel_reason, gross_value, fees`

---

### STORY-2.11: Paper portfolio engine

**Points:** 5 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement `app/paper.py`: the authoritative paper portfolio. Maintains cash, positions, orders, fills, equity curve in SQLite with transactional integrity. No broker dependency.

**Acceptance Criteria:**
- [ ] `PaperPortfolio.__init__(store, config, clock)` — loads persisted state or initializes new
- [ ] `initialise(starting_equity, start_date)` — sets cash, creates first equity curve point
- [ ] `process_risk_actions(actions, bar, quote)` — executes risk exits via fill model
- [ ] `process_entry_orders(candidates, bar, quote)` — creates orders, fills via fill model
- [ ] `mark_to_market(date, market_data)` — updates position.current_price, records equity curve point
- [ ] `self_consistency_check()` — asserts: `cash + Σ(shares * current_price) == equity_curve.last()`
- [ ] All write operations are in a single SQLite transaction (rollback on error)
- [ ] `equity_curve_point(equity, date)` — appends to SQLite equity_curve table
- [ ] Positions traced to fills → orders → decisions (I1, no orphans)
- [ ] Test: full day cycle (risk + entry + fill + mark) produces consistent state; invalid state triggers halt

**Technical Details:**
- Portfolio operates on a daily cycle: `T` close → decide → queue orders → `T+1` open → fill → mark
- Transactional pattern:
  ```python
  with self.store.transaction():
      risk_actions = evaluate_risk(positions, bar, config)
      fills = [fill_stop_order(action, bar, config) for action in risk_actions]
      for fill in fills:
          self._apply_fill(fill)
      self.mark_to_market(date)
      self.self_consistency_check()
  ```
- Equity curve: `CREATE TABLE equity_curve (date DATE PK, equity REAL, cash REAL, exposure REAL, dd_from_peak REAL)`
- Position table: `position_id, symbol, shares, entry_price, current_price, stop_price, trail_price, highest_price, trail_activated, partial_taken, entry_date, sector, decision_id`

---

### STORY-2.12: Shadow ablation books

**Points:** 3 | **Priority:** P1 | **Status:** 📝

**Description:**
Implement `app/shadow.py`: shadow books that run the same fill model with mechanism toggles. RULES_ONLY (permanent baseline), NO_INSIDER, NO_CROWDING_VETO, plus SPY buy-and-hold curve.

**Acceptance Criteria:**
- [ ] `ShadowBook.__init__(book_type, mechanisms_toggle: dict, store, config, clock)` — parallel paper portfolio with toggled mechanisms
- [ ] Three shadow books per DESIGN §8:
  - `RULES_ONLY`: M5 boost = 0, M6 veto disabled, M5 score = 0
  - `NO_INSIDER`: M5 disabled entirely (boost = 0)
  - `NO_CROWDING_VETO`: M6 disabled (never blocks)
- [ ] Each shadow book runs `process_risk_actions`, `process_entry_orders`, `mark_to_market` identically to paper
- [ ] Books are stored with prefix: `positions_rules_only`, `positions_no_insider`, etc.
- [ ] SPY buy-and-hold curve: `SPYBnH` book that buys SPY on day 1 and holds
- [ ] All books update on every pipeline run, including halted ones (I11)
- [ ] Ablation comparison: `ShadowBook.compare(paper_book, shadow_books, date)` computes walk-forward Sharpe difference
- [ ] Test: NO_INSIDER book has different positions than paper book (when insider clusters exist); all books mark correctly on the same data

**Technical Details:**
- Shadow books share the same `Store` port under different table namespaces
- Mechanism toggle is a dict: `{"insider_boost": False, "crowding_veto": False}` — passed through the pipeline
- Ablation comparison function: for each mechanism, compare its ablation book's Sharpe vs the PAPER book over a rolling 6-month window
- If a mechanism's ablation book outperforms for 2 consecutive quarters → flag for removal
- SPY BnH: buys at the first portfolio date at the opening price of SPY, holds, collects dividends (from EODHD calendar)

---

### STORY-2.13: Backtester (event-driven, no vectorbt)

**Points:** 3 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement `app/backtest.py`: event-driven backtester that runs the same domain/fills pipeline over historical data. Not vectorbt — path-dependent decisions require daily-step simulation.

**Acceptance Criteria:**
- [ ] `Backtester.run(start_date, end_date, symbols, config) → BacktestResult`
- [ ] Single loop: for each date, ingest bars → derive → risk → decide → order → fill → mark
- [ ] Uses `VirtualClock` and `FixtureMarketData` (same as replay, but over full history range)
- [ ] Same fill model (`domain/fills.py`) as paper — costs identical by construction (I8)
- [ ] Output: `BacktestResult(equity_curve, all_decisions, all_fills, events, metrics)`
- [ ] Metrics computed: CAGR, max DD, Sharpe (0% RF), Sortino, exposure-adjusted return, turnover, win rate, payoff ratio, avg_hold_days
- [ ] 10 years of 50 symbols completes in <60 seconds
- [ ] Test: hand-computed 5-trade scenario produces exact fills and P&L; backtest of 1-year SPY-only matches buy-and-hold return within slippage

**Technical Details:**
- Loop structure:
  ```python
  clock = VirtualClock(start_date)
  portfolio = PaperPortfolio(config)
  while clock.today() <= end_date:
      date = clock.market_date()
      bars = market_data.read_bars_for_date(date)
      state = derive.update_all(bars, prev_state)
      regime = m2.detect(...)
      risk_actions = risk.evaluate_all(portfolio.positions, ...)
      portfolio.process_risk_actions(risk_actions, ...)
      candidates = pipeline.evaluate_candidates(universe, state, regime, ...)
      portfolio.process_entry_orders(candidates, ...)
      portfolio.mark_to_market(date)
      clock.advance(1)
  ```
- Performance optimization: batch bar reads by date, vectorize indicator updates
- Metrics use `numpy` for computation — CAGR: `(final_equity / initial_equity) ** (1 / years) - 1`, Sharpe: `mean(daily_returns) / std(daily_returns) * sqrt(252)`

---

### STORY-2.14: Daily pipeline (orchestrator)

**Points:** 5 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement `app/pipeline.py`: the daily-run orchestrator that sequences ingest → validate → derive → regime → risk → decide → order → persist. One function called by `alpha-quant run`, `alpha-quant replay`, and `alpha-quant backtest`.

**Acceptance Criteria:**
- [ ] `DailyPipeline.run(date, market_data, store, clock, config, book_type="PAPER", mechanism_toggles=None) → RunResult`
- [ ] Sequence matches DESIGN §13 exactly:
  1. Ingest delta data from all sources (or use fixture data for replay)
  2. Validate ingested data (gaps, stale, quarantines)
  3. Derive incremental indicator state
  4. Detect regime (M2)
  5. Evaluate risk (stops, trails, takes, drawdown, daily loss)
  6. Process risk actions (exit orders)
  7. Decide: universe (M1) → quality (M4) → crowding (M6) → blackout (M7) → score (M3, M5) → rank (M8)
  8. Process entry orders (for vacancies)
  9. Queue T+1 orders
  10. Persist decisions, orders, events
  11. Run self-consistency check
- [ ] Degradation: if a connector fails, pipeline continues with SOURCE_DEGRADED events
- [ ] DATA_HALT: pipeline stops if staleness halt is set
- [ ] Shadow books run after paper book, using same ingested data
- [ ] Test: fixture replay produces exact expected event sequence; missing connector data does not crash pipeline

**Technical Details:**
- Pipeline is dependency-injected: receives all adapters at construction time
- `RunResult`: `run_id, date, book, decisions_count, fills_count, events, errors, halted: bool`
- Shadow books: loop over configured book types, instantiate with mechanism toggles, run same pipeline
- All errors are caught at the pipeline level, logged, and emitted as events — a single mechanism failure never crashes the entire run
- Weekly rebalance: step 7 considers filling all vacancies (not just risk-exited slots) on the designated day

---

### STORY-2.15: Self-consistency & invariants

**Points:** 1 | **Priority:** P0 | **Status:** 📝

**Description:**
Implement the self-consistency assertion engine (DESIGN §9.3, §16). Run after every fill batch. Violation = software bug = full halt.

**Acceptance Criteria:**
- [ ] `SelfConsistencyChecker.check(portfolio, store) → list[ConsistencyViolation]`
- [ ] Checks:
  - `cash + Σ(shares * mark_price) == equity_curve.last_equity` (within 1 cent tolerance)
  - Every position traces to an order with a Decision
  - Every fill traces to an order
  - No orphaned orders or fills
  - Per-position risk-at-stop ≤ 2% equity at order time (I5)
  - Gross exposure ≤ configured cap (I6)
- [ ] Violation → `ConsistencyViolation` event + halt lockfile
- [ ] `alpha-quant status` shows "HALTED: self-consistency failure" with violation details
- [ ] Test: manually corrupt position SQLite → violation detected; inject orphan order → violation detected

**Technical Details:**
- Run after every fill batch (both risk exits and entries)
- Tolerance for floating-point: `abs(cash + mark_value - equity) < 0.01`
- Halt via lockfile: write `data/.HALT` with JSON: `{reason, run_id, date, violations}`
- Pipeline checks for halt file at start and before every write operation

---

## Epic 3: Alternative Data Signals

**Duration:** Weeks 5–6 | **Dependencies:** P0, P1 (connectors), P2 (domain) | **Size:** 18 points

Add insider trading (M5) and crowding veto (M6) signals. Activate all three shadow books. Implement source degradation fallbacks.

---

### STORY-3.1: Insider cluster signal (M5)

**Points:** 3 | **Priority:** P1 | **Status:** 📝

**Description:**
Implement M5 insider cluster signal: detect clusters of insider buying (≥2 officers/directors, ≥$200k net value in 30 days) and produce a score boost for M8.

**Acceptance Criteria:**
- [ ] `M5InsiderScore.evaluate(symbol, insider_transactions, lookback_days=30) → InsiderVerdict`
- [ ] Verdict: `{"cluster_detected": bool, "score_boost": float, "details": dict}`
- [ ] Cluster detection: ≥2 distinct officers or directors filing buys with net value ≥ $200k in 30 days
- [ ] Score boost: 0.15 if cluster detected, 0.0 otherwise
- [ ] When OpenInsider source is degraded: boost = 0, emit SOURCE_DEGRADED event (fail-soft)
- [ ] Test: fixture with 3 officers buying $500k total → cluster detected; single insider buying $50k → no cluster; degraded source → score 0

**Technical Details:**
- Cohen/Malloy/Pomorski (2012) methodology: insider buy clusters > $200k are significant predictors
- Only consider open-market purchases (transaction type "P" or "Purchase")
- Exclude option exercises and grants
- Filter by title: only officers (CEO, CFO, COO, etc.) and directors — not large shareholders (10%+)

---

### STORY-3.2: Crowding veto (M6)

**Points:** 2 | **Priority:** P1 | **Status:** 📝

**Description:**
Implement M6 crowding veto: use Reddit mention z-score to block entries for symbols with extreme social media attention (z > 3). Count arithmetic only — no LLM sentiment.

**Acceptance Criteria:**
- [ ] `M6CrowdingVeto.evaluate(symbol, mention_data) → CrowdingVerdict`
- [ ] Verdict: `{"blocked": bool, "z_score": float, "reason": Optional[str]}`
- [ ] Block if 30-day mention z-score > 3.0
- [ ] Block duration: 10 trading days from detection
- [ ] When Reddit source degraded: block lifted, emit SOURCE_DEGRADED event, raise entry bar (increase M3 threshold by 20%)
- [ ] Test: fixture with mention spike (z=4.5) → blocked with 10-day duration; normal mentions (z=0.5) → not blocked; degraded source → fail-open with raised bar

**Technical Details:**
- Z-score: `(current_day_count - mean_30d) / std_30d`
- Baseline stored in SQLite: `mention_baseline: symbol, mean, std, last_updated`
- 30-day window: rolling window, updated daily
- Block state in SQLite: `crowding_block: symbol, blocked_until_date, reason`
- M6 is a hard veto (not a score) — blocked symbols cannot enter regardless of other scores

---

### STORY-3.3: Shadow ablation books — NO_INSIDER + NO_CROWDING_VETO

**Points:** 3 | **Priority:** P1 | **Status:** 📝

**Description:**
Activate the remaining two shadow ablation books (NO_INSIDER, NO_CROWDING_VETO) and implement the comparison/flagging mechanism.

**Acceptance Criteria:**
- [ ] Both shadow books run alongside PAPER on every pipeline execution
- [ ] Each book has correct mechanism toggles:
  - NO_INSIDER: M5 boost always 0
  - NO_CROWDING_VETO: M6 block always false
- [ ] Ablation comparator: `AblationAnalysis.compare(books, config)` computes rolling metrics
- [ ] Output: per-mechanism table of (mechanism, ablation_sharpe, paper_sharpe, diff, flag)
- [ ] Flag condition: any mechanism with ablation beating PAPER for 2 consecutive quarters gets flagged
- [ ] Flagged mechanism: disabled in PAPER book until manual review
- [ ] Test: fake a mechanism underperforming its ablation → flag triggers after 2 quarters of replay

**Technical Details:**
- Ablation comparator runs weekly, stores comparison results in SQLite
- Rolling metrics: 3-month and 6-month windows
- Comparison table: `mechanism, window_start, window_end, paper_sharpe, ablation_sharpe, outperformance, flagged`
- Flagged mechanisms: written to SQLite `mechanism_flags` table, read by pipeline at startup

---

### STORY-3.4: Source degradation fallback integration

**Points:** 2 | **Priority:** P1 | **Status:** 📝

**Description:**
Implement the degradation fallback logic for when alternative data sources are unreachable. Per DESIGN §3.2: degrade-don't-block.

**Acceptance Criteria:**
- [ ] OpenInsider failure → M5 boost = 0, SOURCE_DEGRADED event, no pipeline halt
- [ ] Reddit failure → M6 veto disabled, SOURCE_DEGRADED event, M3 threshold raised by 20%
- [ ] EODHD fundamentals failure → M4 passes with SOURCE_DEGRADED "fundamentals_missing"
- [ ] EODHD earnings calendar failure → M7 blackout window widened by 1 day (conservative)
- [ ] SEC map failure → use last-good cache, SOURCE_DEGRADED event
- [ ] Test: disconnect each source in fixture replay → verify correct fallback behavior, verify pipeline continues

**Technical Details:**
- Degradation state stored in SQLite: `source_degradation: source, since_date, last_ok_date, degradation_payload (JSON)`
- Pipeline reads degradation state at startup for each source
- Fallback behaviors are implemented in the respective mechanism functions, not in the connectors

---

## Epic 4: Narration & Education

**Duration:** Weeks 6–7 | **Dependencies:** P2 (event log) | **Size:** 20 points

Build the LLM narrator, concept card registry, report generators, and Streamlit dashboard.

---

### STORY-4.1: LLM adapter (OpenAI + OpenRouter)

**Points:** 2 | **Priority:** P1 | **Status:** 📝

**Description:**
Implement the LLM port adapter for OpenAI-compatible APIs. Supports OpenAI and OpenRouter via configurable `base_url`. Handles authentication, retry, timeout, structured output parsing.

**Acceptance Criteria:**
- [ ] `LLMAdapter.__init__(provider, model, api_key, base_url, timeout)` — configurable per config.toml
- [ ] `explain(context: NarrationContext) → str` — sends rendered facts to LLM, returns prose
- [ ] `generate_card(concept: ConceptDef) → str` — generates or retrieves concept explanation
- [ ] Uses `httpx` directly (not OpenAI SDK) — one code path for both providers
- [ ] `base_url="https://api.openai.com/v1"` for OpenAI, `"https://openrouter.ai/api/v1"` for OpenRouter
- [ ] Timeout: configurable, default 30s
- [ ] Retry: tenacity exponential backoff, max 3 retries on 5xx/429
- [ ] API key from config (SecretStr), masked in logs
- [ ] Test: mock httpx responses return expected prose; timeout raises clear error; LLM outage → template fallback

**Technical Details:**
- Chat completions call:
  ```python
  POST {base_url}/chat/completions
  {
      "model": model_name,
      "messages": [{"role": "system", "content": system_prompt},
                   {"role": "user", "content": user_message}],
      "temperature": 0.3,  # low temperature for deterministic output
      "max_tokens": 1000
  }
  ```
- System prompt for explain: "You are a financial educator explaining a quantitative trading system to a beginner. Present the following facts in clear, plain English. Do not add any numbers or facts that are not provided below. If you don't understand something, say so."
- User message: rendered NarrationContext as structured text
- Fact-checker (STORY-4.3) runs after LLM returns

---

### STORY-4.2: Narration context builder

**Points:** 3 | **Priority:** P1 | **Status:** 📝

**Description:**
Implement the narration context builder: reads events/lineage, extracts numbers, builds a `NarrationContext` with all data points the LLM is allowed to mention.

**Acceptance Criteria:**
- [ ] `NarrationContextBuilder.build(date, events, decisions, positions, regime, metrics) → NarrationContext`
- [ ] Content:
  - Regime state + reason
  - Data health summary (sources OK, degraded, quarantined)
  - Candidates evaluated, gated vs blocked (with counts and top-3 reasons)
  - Positions opened/closed today
  - Risk map: per-position distance to stop (as % of equity)
  - Equity curve: today, week-ago, month-ago values
  - One "concept of the day" from the rotation
- [ ] All numbers are extracted from events, never from LLM or raw data
- [ ] NarrationContext is a frozen pydantic model — serializable and auditable
- [ ] Test: fixture replay produces NarrationContext with all fields populated; verify every number appears in source events

**Technical Details:**
- Event extraction queries: `events_by_run_id()`, `events_by_type("RegimeChanged")`, etc.
- Risk map: for each position, compute `(current_price - stop_price) / equity * 100` — "AAPL is 0.8% of equity from its stop"
- Concept rotation: cycle through concept list, track `concept_log` in SQLite, respect `concept_repeat_limit`

---

### STORY-4.3: Fact-checker (post-LLM verification)

**Points:** 2 | **Priority:** P1 | **Status:** 📝

**Description:**
Implement the fact-checker that verifies every number in LLM output exists in the source data (NarrationContext). On mismatch → fall back to plain template.

**Acceptance Criteria:**
- [ ] `FactChecker.verify(llm_output: str, context: NarrationContext) → VerificationResult`
- [ ] Extract all numbers from LLM output via regex (`\d+\.?\d*`)
- [ ] Check each number against allowable values in NarrationContext
- [ ] Allowlist: all numbers that appear in context (prices, percentages, dates, counts)
- [ ] If any number in output is NOT in allowlist → `verdict = "FAIL"`
- [ ] On verification failure → discard LLM output, return template narration
- [ ] Test: LLM output with hallucinated number → fail and fall back; output with only context numbers → pass

**Technical Details:**
- Number extraction: `re.findall(r'\b\d+(?:\.\d+)?(?:%|bps|USD)?\b', llm_output)`
- Allowlist: extract all numeric values from NarrationContext serialization (JSON dump, regex extract)
- Template fallback: "On {date}, the regime was {regime}. {n} candidates were evaluated. {m} positions are active." — simple string formatting

---

### STORY-4.4: Concept card registry (~20 cards)

**Points:** 3 | **Priority:** P1 | **Status:** 📝

**Description:**
Write ~20 hand-crafted concept cards covering key trading concepts. These are static Markdown files read by the narrator, not generated by LLM.

**Acceptance Criteria:**
- [ ] Registry at `alpha_quant/concepts/` with ~20 `.md` files
- [ ] Required cards: "What is ATR?", "How stop-loss works", "What is regime?", "Position sizing explained", "Drawdown vs loss", "Slippage", "Paper vs live trading", "What is RSI?", "MACD explained", "Earnings blackout", "Insider trading signals", "Crowding / social media risk", "Diversification & sector limits", "Why we don't day trade", "What is a fill model?", "Trailing stops", "Risk-reward ratio", "Compounding", "Tax efficiency (long-term)", "How to read the daily journal"
- [ ] Each card: title, difficulty (beginner/intermediate), 2-3 paragraph explanation, "key takeaway" callout
- [ ] Cards are plain language, no math notation beyond basic arithmetic, no jargon without explanation
- [ ] Registry has a manifest: `concepts.json` mapping card_name → file_path, difficulty, prerequisites
- [ ] Test: all 20 cards exist and parse as valid Markdown

**Technical Details:**
- Markdown format with frontmatter:
  ```markdown
  ---
  id: atr
  title: What is ATR (Average True Range)?
  difficulty: beginner
  prereqs: []
  ---
  
  Content here...
  ```
- Cards stored in `alpha_quant/concepts/{id}.md`
- Narrator reads cards on demand, passes through LLM for plain-English polish (after fact-check)

---

### STORY-4.5: Daily journal generator

**Points:** 2 | **Priority:** P1 | **Status:** 📝

**Description:**
Generate the daily journal: regime, actions, risk map, concept card. Output is Markdown, ready for email or dashboard.

**Acceptance Criteria:**
- [ ] `DailyJournal.generate(date, context, narration, events) → str` (Markdown)
- [ ] Sections:
  - **Market Overview**: regime, SPY performance, VIX, breadth
  - **Data Health**: sources green/yellow/red
  - **Today's Actions**: positions opened/closed with rationale
  - **Risk Map**: table of position, distance to stop, % of equity at risk
  - **Non-Actions**: "No entries today — regime is CAUTION" (negative-space narration)
  - **Concept of the Day**: one expandable concept card
  - **Key Numbers**: portfolio value, cash, exposure, daily return
- [ ] Output written to SQLite `journal_entries` table (date, markdown)
- [ ] Test: fixture replay produces readable 6-month journal; verify sections present

**Technical Details:**
- Markdown format, not HTML (Simon Willison's style recommendations: plain, readable, machine-parseable)
- Concept of the day: rotate through the 20 cards; track last-shown in concept_log
- Risk map table: `| Symbol | Distance to Stop | % of Equity | Sector |`
- Non-actions: "No new positions. {n} candidates passed gates but {regime} regime limited entry." — built from events

---

### STORY-4.6: Weekly and monthly reports

**Points:** 2 | **Priority:** P1 | **Status:** 📝

**Description:**
Generate weekly review and monthly performance reports. Monthly includes ablation scoreboard and mechanism attribution.

**Acceptance Criteria:**
- [ ] `WeeklyReport.generate(date) → str` — rebalance rationale, candidate funnel stats, book deltas, upcoming blackouts, market recap
- [ ] `MonthlyReport.generate(date) → str` — paper vs SPY vs shadow books (scoreboard), attribution by mechanism, risk stats, turnover/cost drag, config change log, paper-vs-live caveat, learning recap from concept_log
- [ ] Monthly report includes:
  - CAGR, Sharpe, Sortino, max DD for PAPER + all shadows
  - Attribution: "M5 (insider) contributed +0.8% vs RULES_ONLY baseline"
  - Turnover and cost drag (total slippage + spread costs for the month)
  - Concept cards reviewed this month (from concept_log)
  - Paper-vs-live caveat: bolded callout
- [ ] Reports are Markdown, stored in SQLite, accessible via `alpha-quant report --weekly/--monthly`
- [ ] Test: fixture replay of 3 months → monthly report with all sections populated; ablation comparisons correct

**Technical Details:**
- Weekly: run on Friday after market close (check `clock.market_date().weekday() == 4`)
- Monthly: run on last trading day of month
- Attribution: compare paper book equity curve to each ablation shadow — difference = mechanism contribution
- Turnover: `(total buys + total sells) / 2 / avg_portfolio_value` — monthly and annualized
- Cost drag: sum of all slippage + spread costs from fill model, divided by total portfolio return

---

### STORY-4.7: Streamlit dashboard

**Points:** 3 | **Priority:** P1 | **Status:** 📝

**Description:**
Build a read-only Streamlit dashboard that reads from the event log and SQLite store. No coupling to pipeline internals — consumes only persisted data.

**Acceptance Criteria:**
- [ ] `streamlit run alpha_quant/app/dashboard.py` launches dashboard
- [ ] Tabs: Overview, Portfolio, Risk, Reports, Concepts
- [ ] Overview tab: equity curve chart, regime indicator, data health, recent events
- [ ] Portfolio tab: current positions table, P&L, sector allocation pie chart
- [ ] Risk tab: stop distances, drawdown chart, VaR estimate, halt status
- [ ] Reports tab: daily journal, weekly/monthly reports in rendered Markdown
- [ ] Concepts tab: browse all concept cards
- [ ] Dashboard is read-only — no buttons/toggles that affect the running system
- [ ] Test: fixture data produces populated dashboard; verify all charts render without errors

**Technical Details:**
- Stack: Streamlit + altair/plotly for charts + markdown rendering
- Data sources: SQLite store (positions, equity_curve, events) and journal tables
- No network calls, no pipeline interaction — pure read from local state
- Auto-refresh: `st_autorefresh` every 60 seconds when running live

---

### STORY-4.8: `ask` command — query recorded decisions

**Points:** 2 | **Priority:** P1 | **Status:** 📝

**Description:**
Implement `alpha-quant ask "why didn't you buy TSLA?"` — answers from recorded `CandidateBlocked` events. The LLM presents recorded reasoning, never generates new reasoning.

**Acceptance Criteria:**
- [ ] `alpha-quant ask "why didn't you buy TSLA?"` responds with recorded reasoning from the last evaluation date
- [ ] Query: search decisions for TSLA → find `CandidateBlocked` event(s) → present reasons
- [ ] If TSLA was never a candidate: "TSLA was not in the universe because [M1 reason]"
- [ ] If TSLA was evaluated and passed: "TSLA passed all gates but ranked below the top {n} candidates. The top candidate was {top_symbol} (score {score})."
- [ ] `ask` about any symbol: shows most recent decision reasoning
- [ ] `ask` about a concept: "explain ATR" → returns concept card content
- [ ] LLM is used only to polish the presentation of recorded facts — no new reasoning
- [ ] Test: fixture with blocked TSLA → ask returns correct reason; fixture with unkown symbol → says not in universe

**Technical Details:**
- Query path:
  1. Look up symbol in last N days of events
  2. Find `CandidateBlocked(symbol=TSLA)` → extract reason
  3. Find `CandidateScored(symbol=TSLA)` → extract score, ranking
  4. Format as structured data for LLM → polish prose
  5. Pass through FactChecker (STORY-4.3)
- If no events for the symbol: return template: "I don't have a record of evaluating TSLA. It may not be in my universe."
- Concept lookup: search concept card registry for the key term

---

## Epic 5: Live Data Operations

**Duration:** Weeks 7–8 | **Dependencies:** P1 (real connectors), P4 (monitoring) | **Size:** 16 points

Activate real data connectors on schedule, implement alerting, ops commands, backup, and unattended operation validation.

---

### STORY-5.1: Real connector configuration & activation

**Points:** 3 | **Priority:** P1 | **Status:** 📝

**Description:**
Wire up the real connectors (EODHD, Alpaca, SEC, OpenInsider, Reddit) for live operation. API keys from config, rate-limiting active, vault-writing enabled.

**Acceptance Criteria:**
- [ ] All 5 connectors load with real API keys from config (SecretStr)
- [ ] `alpha-quant run --live` runs the full pipeline with real connectors
- [ ] Rate limiters are active (respect source budgets)
- [ ] Vault stores raw responses before parsing (I4)
- [ ] Fixture-vs-real adapter parity test: real connector + cached vault response produces same canonical output as fixture replay
- [ ] API keys masked in logs: `EODHD key=****2345`
- [ ] Connection test: `alpha-quant status --check-connections` pings each source and reports green/yellow/red

**Technical Details:**
- Real adapters are selected by pipeline based on `config.data.mode = "live"` vs `"fixture"`
- Factory function: `def create_market_data(config) -> MarketData: if config.mode == "live": return EODHDConnector(config) else: return FixtureMarketData(config)`
- Connection check: lightweight health endpoint or `HEAD` request per source

---

### STORY-5.2: Scheduling (APScheduler)

**Points:** 2 | **Priority:** P1 | **Status:** 📝

**Description:**
Set up APScheduler to run the daily pipeline at 17:30 ET every trading day. With cron fallback for resilience.

**Acceptance Criteria:**
- [ ] Scheduler fires daily at 17:30 ET (21:30 UTC / 22:30 UTC daylight)
- [ ] Scheduler checks market calendar: only runs on trading days
- [ ] Run is idempotent: if scheduler fires twice for same date, second run is a no-op (check run_id)
- [ ] Scheduler log to file: `logs/scheduler.log` (rotating, 30-day retention)
- [ ] Cron fallback: if scheduler process dies, cron job picks up (crontab entry documented)
- [ ] Test: simulated time change across DST boundary; duplicate trigger → no-op

**Technical Details:**
- APScheduler `CronTrigger` with timezone = America/New_York, hour=17, minute=30
- Use `BackgroundScheduler` with `logging` integration
- Idempotency: check SQLite `runs` table for existing run with today's date
- Cron fallback entry (to be added manually via `crontab -e`):
  ```cron
  30 21 * * 1-5 cd /path/to/alpha-quant && alpha-quant run --live --if-not-already-run
  ```

---

### STORY-5.3: Alerting & notifications

**Points:** 2 | **Priority:** P1 | **Status:** 📝

**Description:**
Implement alerting for critical events: halt conditions, source degradation, drawdown thresholds, and daily run completion/failure.

**Acceptance Criteria:**
- [ ] Alerts triggered by event type:
  - `DATA_HALT` → immediately (email + desktop notification)
  - `SOURCE_DEGRADED` → after 2 consecutive days (daily digest)
  - `DRAWDOWN_LADDER_TRIPPED` → immediately
  - `CONSISTENCY_VIOLATION` → immediately (software bug)
  - `PIPELINE_FAILED` → immediately
  - Daily run success/failure → daily digest
- [ ] Alert channel: console (structlog), file log, optional email (smtplib if configured)
- [ ] `alpha-quant status --alerts` shows recent alerts
- [ ] Test: force a data halt → alert fires; drawdown tripped → alert fires; pipeline failure → alert fires

**Technical Details:**
- Alert levels: `CRITICAL` (halt, violation, drawdown), `WARNING` (degraded 2+ days), `INFO` (run completed, source degraded 1 day)
- Alert structure: `Alert(level, source, title, message, timestamp, acknowledged: bool)`
- Email: optional SMTP config in config.toml — `[alerts.email]` section with `enabled, smtp_server, from, to`
- Desktop notification: macOS `osascript -e 'display notification "..." with title "Alpha-Quant"'` or `terminal-notifier`

---

### STORY-5.4: Ops commands — status, halt, resume

**Points:** 2 | **Priority:** P1 | **Status:** 📝

**Description:**
Implement operational commands: `alpha-quant status` (full system status), `halt` (kill switch), and `resume` (clear halt).

**Acceptance Criteria:**
- [ ] `alpha-quant status` prints:
  - System state: RUNNING / HALTED / IDLE
  - Last run: date, result, duration
  - Data health: per-source status + staleness
  - Portfolio: equity, cash, exposure, positions count
  - Regime: current + days in regime
  - Alerts: unacknowledged count
  - Uptime: days since last restart
- [ ] `alpha-quant halt "reason"` creates halt lockfile with reason
- [ ] `alpha-quant resume` clears halt lockfile (requires confirmation)
- [ ] `alpha-quant status --json` outputs machine-readable JSON
- [ ] Test: halt → status shows HALTED; resume → status shows IDLE; halt → pipeline refuses to run

**Technical Details:**
- Halt lockfile: `data/.HALT` — JSON with `{reason, timestamp, run_id}`
- Pipeline checks for `.HALT` at startup: if exists and not expired, refuse to run
- Status reads from: SQLite (last run, portfolio, regime), vault (data health), halt file

---

### STORY-5.5: Backup & recovery

**Points:** 2 | **Priority:** P1 | **Status:** 📝

**Description:**
Implement backup routine for critical data: SQLite state store + vault manifest. Document recovery procedure.

**Acceptance Criteria:**
- [ ] `alpha-quant backup` creates compressed archive of:
  - SQLite state store (`.backup` command)
  - Vault manifest (DuckDB)
  - Config file (redacted copy)
- [ ] Backup path: `backups/alpha-quant-{date}-{sha}.tar.zst`
- [ ] Automatic daily backup after pipeline run
- [ ] Retention: keep last 30 daily backups, last 12 monthly
- [ ] Recovery document: `docs/ops/RECOVERY.md` with step-by-step restore procedure
- [ ] Test: backup → delete SQLite → restore → verify data integrity

**Technical Details:**
- SQLite backup: `sqlite3 alpha_quant.db ".backup backup_path/alpha_quant-{date}.db"` (hot backup, WAL mode supports concurrent reads)
- Parquet/canonical data: not backed up per-se (re-parseable from vault), but vault is cheap to back up
- Recovery procedure (documented):
  1. Stop scheduler
  2. Copy backup to data directory
  3. Verify self-consistency
  4. Resume scheduler
  5. Run `alpha-quant status` to confirm

---

### STORY-5.6: Unattended operation validation

**Points:** 3 | **Priority:** P1 | **Status:** 📝

**Description:**
Validate that the system runs unattended for 2 weeks without human intervention. Chaos test: kill mid-run, restart, force staleness.

**Acceptance Criteria:**
- [ ] Chaos test 1: `kill -9` the running process mid-ingest → restart → verify idempotent re-run (no duplicate data, no corruption)
- [ ] Chaos test 2: disable network → pipeline logs SOURCE_DEGRADED for all sources → DATA_HALT triggered by staleness → restore network → next run recovers
- [ ] Chaos test 3: modify SQLite directly (corrupt a position row) → self-consistency check catches → HALT → restore from backup
- [ ] Chaos test 4: disk full → graceful error, log, pipeline halt
- [ ] All tests pass without human intervention (beyond starting the test)
- [ ] Log of 2-week unattended run shows no crashes, clean daily runs, all halt conditions recover

**Technical Details:**
- Chaos tests are scripts in `tests/chaos/` that simulate failure conditions
- Disk full test: use a small tmpfs or quota limit via `pytest` fixture
- Recovery from kill: no partial writes (SQLite WAL + vault append-only guarantee atomicity per operation)
- Run verification: `pytest tests/chaos/` as part of CI (not golden, but integration)

---

## Epic 6: Evaluation & Optimization

**Duration:** ≥3 months | **Dependencies:** All prior | **Size:** Continuous

Run paper and shadow books daily. Evaluate mechanism performance. Make keep/kill/broker decisions.

---

### STORY-6.1: Mechanism ablation analysis

**Points:** 8 (ongoing) | **Priority:** P2 | **Status:** 📝

**Description:**
After ≥3 months of daily paper trading, produce definitive mechanism ablation analysis. Every mechanism compared to its ablation book.

**Acceptance Criteria:**
- [ ] Per-mechanism report: Sharpe, CAGR, max DD, win rate for PAPER vs each ablation book
- [ ] Statistical significance: bootstrap test (1000 resamples) on Sharpe difference
- [ ] Flagged mechanisms: any with p > 0.10 (not significantly better than ablation) marked for removal
- [ ] Cost analysis: turnover, slippage, spread costs per mechanism
- [ ] Recommendation: keep, modify, or remove each mechanism
- [ ] Documented in `docs/evaluation/MECHANISM_ANALYSIS.md`

**Technical Details:**
- Bootstrap test: sample daily returns with replacement 1000×, compute Sharpe for each sample, compare distributions
- `scipy.stats` for bootstrap if available; otherwise implement simple resampling with numpy

---

### STORY-6.2: Parameter sensitivity analysis

**Points:** 5 | **Priority:** P2 | **Status:** 📝

**Description:**
Systematically test the ≤3 tunable parameters across their ranges via walk-forward analysis.

**Acceptance Criteria:**
- [ ] Parameters to test: `stop_atr_mult`, `risk_per_trade_pct`, `max_positions`
- [ ] Walk-forward: 3-year train, 1-year test, roll forward
- [ ] Parameter grid: 3 values each → 27 combinations
- [ ] Output: parameter surface plots (Sharpe vs params), optimal region, stability measure
- [ ] Recommendation: default parameter set + sensitivity bounds
- [ ] Documented in `docs/evaluation/PARAMETER_ANALYSIS.md`

**Technical Details:**
- Walk-forward: walk-forward cross-validation — 3y train / 1y test, step by 6 months
- Grid search: simple nested loops, not optimization (≤3 params × 3 values = 27 combos)
- Stability: coefficient of variation of Sharpe across walk-forward windows

---

### STORY-6.3: Broker decision & live-gate criteria

**Points:** 5 | **Priority:** P2 | **Status:** 📝

**Description:**
Evaluate whether to implement the broker port and go live. Per DESIGN §9.4 and §14 live-gate criteria.

**Acceptance Criteria:**
- [ ] Live-gate criteria evaluated (documented):
  - ≥3 months of paper trading
  - Sharpe > 0.5 (PAPER book)
  - Max DD < 20%
  - All mechanisms non-negative vs ablation (or flagged for removal)
  - Self-consistency violations: zero
  - Unattended operation: ≥2 weeks without intervention
- [ ] If all gates pass → recommendation: implement broker adapter
- [ ] If any gate fails → recommendation: address-specific failure, extend evaluation
- [ ] Broker adapter scope: Alpaca Broker API (trading module), defined in DESIGN §9.4
- [ ] Decision documented in `docs/evaluation/BROKER_DECISION.md`

**Technical Details:**
- Broker adapter would implement: `submit_order(market_order/limit_order)`, `cancel_order(id)`, `positions()`, `account()` — mapping from domain models to Alpaca SDK
- Reconciliation: compare broker positions to paper book daily → alert on divergence
- Start with small size: $10K, 50% of paper sizing
- If broker decision is NO: evaluation continues; re-evaluate quarterly

---

## Appendix: Issue Labels & Workflow

### Labels

| Label | Meaning |
|-------|---------|
| `epic` | Top-level phase/theme |
| `story` | User/technical story |
| `task` | Sub-task within a story |
| `bug` | Bug fix |
| `tech-debt` | Refactoring, test improvements |
| `blocked` | Waiting on dependency |
| `question` | Needs clarification |
| `priority/p0` | Must have for release |
| `priority/p1` | Should have |
| `priority/p2` | Nice to have |
| `size/xs` | 1 point (trivial) |
| `size/s` | 2 points (small) |
| `size/m` | 3 points (medium) |
| `size/l` | 5 points (large) |
| `size/xl` | 8 points (very large, needs split) |
| `domain/backend` | Backend/data work |
| `domain/quant` | Quant/domain logic work |
| `domain/frontend` | Dashboard/reporting work |
| `domain/ops` | Operations/DevOps work |

### Workflow

```
Backlog (📝) → Refining (🔍) → In Progress (🏗) → Review → Done (✅)
                  ↑                        │
                  └───── Blocked (❌) ─────┘
```

### Sprint Template

Sprint length: 1 week (adjustable)

**Sprint goal:** 1–2 stories from highest-priority epic

**Capacity:** Team velocity estimate: 10–15 points/week (3 devs, accounting for meetings, review, context switching)

**Sprint ceremonies:**
- Mon 10:00 — Sprint planning (1h): select stories, define tasks
- Daily 9:30 — Standup (15min)
- Fri 15:00 — Review (30min): demo working increment
- Fri 15:30 — Retro (30min): what worked, what to improve

# Refactoring Punch List — P6.R Post-Dashboard UX/IA Refinement

## P0 — Must Fix Before Production

### P0.1: Fix `except ValueError, TypeError:` syntax bug (3 locations)
- **Files:** `alpha_quant/domain/_normalize_helpers.py:15,40,68`
- **Change:** `except ValueError, TypeError:` → `except (ValueError, TypeError):`
- **Effort:** 5 min, 1 file, 3 lines
- **Rationale:** Python 2 comma-separated syntax catches `ValueError` only; `TypeError` is bound to the variable name and **not caught**. Python 3.14 targets make this a real bug. (Note: original locations in `base_connector.py` and `store/state.py` were already fixed; these three remain.)

## P1 — High Priority

### P0.2: Composite score formula inconsistency — 3 different weighting formulas
- **Files:** `alpha_quant/domain/ranking.py:63-73`, `alpha_quant/domain/loop_helpers.py:131`, `alpha_quant/domain/technical.py:39-46`
- **Change:** Consolidate to a single `compute_composite(scores, components)` in `domain/scoring.py`. `ranking.py:_compute_composite` uses `0.60/0.25/0.15`, `loop_helpers.py:score_candidate` uses `0.70/0.30`, `technical.py:score` uses `0.3125/0.25/0.1875/0.125/0.125`. `rank()` recomputes composite overwriting the value set during scoring — final score depends on ordering of function calls.
- **Effort:** Medium (2 files, ~30 lines)
- **Rationale:** Bug — can produce different final rankings depending on which pipeline path is taken

## P1 — High Priority

### P1.1: Fix adapter → app import violation in llm_adapter.py
- **Files:** `alpha_quant/adapters/real/llm_adapter.py:9`
- **Change:** Move `LLMConfig` to a shared domain/ports types module, or create a port-level config Protocol to avoid runtime import from `alpha_quant.app.config`
- **Effort:** Small (2 files, ~10 lines)
- **Rationale:** Only hard hexagonal architecture violation (runtime import). 5 other adapters have type-checking-only soft violations.

### P1.2: Remove unused `hypothesis` dev dependency
- **Files:** `pyproject.toml`
- **Change:** Remove `hypothesis` from dev dependencies
- **Effort:** 1 min
- **Rationale:** Zero imports in any source or test file. Dead weight in lockfile.

### P1.3: Pipeline — call `write_halt()` when validation HALT occurs
- **Status:** ✅ Already implemented (pipeline.py:202, scheduler.py:59)

### P1.4: Wire LLM adapter in factory
- **Status:** ✅ Already implemented (factory.py:116 `create_llm`)

### P1.5: Wire Store adapter in factory
- **Status:** ✅ Already implemented (factory.py:110 `create_store`)

### P1.6: Wire EventSink adapter in factory
- **Status:** ✅ Already implemented (factory.py:104 `create_event_sink`)

### P1.9: Implement missing event emissions
- **Status:** ✅ Done — StalenessHaltSet and DataIngested added (all 20 event types now emitted)

### P1.10: Graduate insider signal from binary to continuous
- **Status:** ✅ Already implemented — `insider_signal.py` uses proportional `total_value / market_cap` scoring with sell penalty

### P1.11: Add sector concentration check in ranking
- **Status:** ✅ Already implemented — `ranking.py:42-53` enforces `max_sector_pct=0.25`

### P1.14: Fix RSI scoring — replace discrete ranges with continuous function
- **Status:** ✅ Already implemented — `technical.py:90-95` uses Gaussian centered at 52, sigma 22

### P1.15: Add SPY benchmark to backtest metrics
- **Status:** ✅ Already implemented (backtest.py:62-64, 405-414)

### P1.17: Implement CLI stubs — journal, report, backtest
- **Status:** ✅ Already implemented (cli.py:175 cmd_backtest, 338 cmd_journal, 372 cmd_report)

### P1.18: Integration/E2E tests for critical paths
- **Status:** ✅ Done — 5 backtest integration tests added (PR #406)

### P1.19: Hardcoded event-type strings in dashboard (22 occurrences)
- **Files:** `alpha_quant/app/dashboard.py` (lines 174, 256-259, 352, 396-399, 706-708)
- **Change:** Import event classes from `alpha_quant.domain.events` and use their `event_type` defaults instead of hardcoded strings. Extract repeated event strings to module-level constants.
- **Effort:** Small (1 file, ~15 lines)
- **Rationale:** Silent breakage if event types change in `events.py`. 8 unique strings duplicated 22 times.

### P1.20: Duplicate gate logic in pipeline and ranking
- **Status:** ✅ Not a bug — pipeline checks emit CandidateBlocked events and enforce composite threshold; ranking checks filter by gate_results. Different concerns, same data.

### P1.21: Canonical Parquet read function duplication (6 near-identical functions)
- **Change:** Extracted `_read_dataset()` helper. ~200 lines → ~50 lines. PR #405.
- **Status:** ✅ Done

### P1.22: Fix ADR-0027 — apscheduler not made optional despite ADR claim
- **Files:** `docs/adr/0027-use-dependency-pruning.md`
- **Change:** Updated ADR-0027 to reflect apscheduler stayed as main dependency (scheduler is core feature)
- **Effort:** Small (1 file, ~5 lines)
- **Status:** ✅ Done
- **Files:** `tests/integration/` (new files)
- **Change:** Store round-trip tests (DuckDB read/write), pipeline with fixture data, paper portfolio lifecycle, backtest metrics correctness
- **Effort:** Large (4-5 new files, ~300 lines)
- **Rationale:** `tests/integration/` is empty. No end-to-end tests exist.

## P2 — Medium Priority

### P2.1: Add `vault_fetch_id` back-reference to canonical Parquet
- **Files:** `alpha_quant/app/store/canonical.py`, `alpha_quant/app/store/schema.py` (canonical schemas + write path)
- **Change:** Add `fetch_id` column to all canonical schemas; populate during write from connector metadata
- **Effort:** Medium (1 file, ~30 lines)
- **Rationale:** No way to trace a canonical bar back to the raw API response. Data lineage is broken.

### P2.2: Fix MentionCount field name inconsistency
- **Status:** ✅ Already consistent — model has `mention_date`, Parquet has `mention_date`

### P2.3: Add missing indexes on events table
- **Status:** ✅ Already implemented (state.py:157-158)

### P2.4: Implement atomic Parquet partition swap
- **Files:** `alpha_quant/app/store/canonical.py`
- **Change:** Currently uses tempdir → rename pattern. Atomicity is adequate for single-machine. Acceptable.
- **Status:** ✅ Already implemented (temp directory + atomic rename)

### P2.5: Fix vault orphan file risk
- **Status:** ✅ Already implemented (vault.py:78 .tmp write + rename after commit)

### P2.6: Config versioning — add `config_version` field
- **Status:** ✅ Already implemented (config.py:184 `config_version: int = 1` with validator)

### P2.7: Volume-anomaly validation in `validate.py`
- **Status:** ✅ Already implemented (volume spike >10x, volume drop <10% of 20d avg)

### P2.8: Make return spike threshold volatility-adjusted
- **Status:** ✅ Already implemented (uses `avg_ret * spike_atr_mult` at validate.py:93)

### P2.9: Remove dead code — `trail_price`, `BacktestResult.decisions`
- **Status:** ✅ Not dead — trail_price used in risk.py/paper.py/store; decisions used in CLI/scheduler/tests

### P2.12: Add JSON config schema generation
- **Files:** `alpha_quant/app/config.py` (or new script)
- **Change:** Call `AppConfig.model_json_schema()` and write to `docs/config-schema.json`
- **Effort:** 10 min, 1 file, ~3 lines
- **Rationale:** Available via Pydantic but never used. Would auto-generate config documentation.

### P2.13: Make drawdown ladder rolling window instead of all-time peak

### P2.14: Duplicated column-name lists across all store mixins
- **Files:** All files in `alpha_quant/app/store/` (position_store, order_store, decision_store, admin_store, journal_store)
- **Change:** Extract shared column-name constants per table. Each column name appears 2-3 times (INSERT, SELECT, model constructor).
- **Effort:** Small (5 files, ~30 lines)
- **Rationale:** Reduces drift risk between read and write column lists.

### P2.15: Re-export-only wrapper in `_loop.py`
- **Files:** `alpha_quant/app/_loop.py:8-18`
- **Change:** Remove pass-through re-exports of `score_candidate`, `compute_atr`, `evaluate_risk_actions`, `get_bar_for_date`, `get_date_bars`, `size_entry`, `bars_up_to` — import directly from `domain.loop_helpers` in consumers.
- **Effort:** Small (2 files, ~10 lines)
- **Rationale:** `_loop.py` adds no logic for these functions. Pure indirection.
- **Files:** `alpha_quant/domain/risk.py`
- **Change:** Add `dd_window_days` config option. When set, measure drawdown from rolling window peak instead of all-time.
- **Effort:** Small (1 file, ~10 lines)
- **Rationale:** Default 15% from all-time peak shuts down new entries permanently after a single crash. Rolling window allows recovery.

## P3 — Documentation & Workflow

### P3.1: Create ADR-0027 — Dependency pruning & tail prune removal
- **Change:** New ADR documenting removal of polars, sqlalchemy, apscheduler; removal of 50-day tail prune; rationale for each
- **Effort:** 30 min, 1 file

### P3.2: Reformat ADRs 0025/0026 to standard MADR template
- **Change:** Convert list-style headers to `## Status / Date / Context / Decision Drivers / Considered Options / Decision Outcome / Consequences / References`
- **Effort:** 20 min, 2 files

### P3.3: Update ADR-0014 — replace SQLite references with DuckDB
- **Change:** Update "reads SQLite via SQLAlchemy Core" → "reads DuckDB via Store port (per ADR-0021)"
- **Effort:** 10 min, 1 file
- **Status:** ✅ Done

### P3.4: Update REFERENCE_ARCHITECTURE.md
- **Change:** Fix Python version (3.12 → 3.14), remove SQLite/polars rows, add ADRs 0019-0026 to sections 5 and 9
- **Effort:** 20 min, 1 file
- **Status:** ✅ Done

### P3.5: Update DESIGN.md stale sections
- **Change:** Fix §3.8 (polars example → remove), §10 (SQLite → DuckDB via Store port)
- **Effort:** 10 min, 1 file
- **Status:** ✅ Done

### P3.6: Update AGENTS.md with missing workflow steps
- **Change:** Add `uv run pytest` to verification step, golden file workflow (`make bless-golden`), note `make check/format/type` as aliases
- **Effort:** 15 min, 1 file
- **Status:** ✅ Done

### P3.7: Update ADR-0015 — remove stale "50-day tail prune" references
- **Status:** ✅ Already current — references are design narrative, not implementation

### P3.8: Update ADR-0026 — correct content hash length
- **Status:** ✅ Done — updated: content_hash = full 64-char hexdigest, fetch_id = [:16]

### P3.9: Update ADR-0021 — stale `app/store.py` path
- **Status:** ✅ Done — updated to `app/store/state.py`

### P3.10: Create ADR for clock virtualization architecture
- **Change:** Created ADR-0028 documenting `ports/clock.py`, `SystemClock`, `VirtualClock`. Invariant I9 (deterministic clock) central to golden replay.
- **Effort:** 30 min, 1 file
- **Status:** ✅ Done

### P3.11: Create ADR for store port decomposition into mixins
- **Change:** Created ADR-0029 documenting the evolution from a single Store interface to 9 specialized mixin classes combined by `CanonicalStore`.
- **Effort:** 20 min, 1 file
- **Status:** ✅ Done

### P3.12: Create ADR for shadow ablation book architecture
- **Change:** Created ADR-0030 documenting the shadow book pattern in `domain/ablation.py` for mechanism evaluation.
- **Effort:** 20 min, 1 file
- **Status:** ✅ Done

### P3.13: Create ADR for halt mechanism (file-based protocol)
- **Change:** Created ADR-0031 documenting `app/halt.py` — write_halt, read_halt, is_halted, clear_halt.
- **Effort:** 15 min, 1 file
- **Status:** ✅ Done
- **Change:** ADR-0021 references `app/store.py` which no longer exists; update to `app/store/state.py`.
- **Effort:** 5 min, 1 file

## Completed Items (from previous refinements, preserved for audit trail)

### P1.R (Resolved)
- P0.3: `normalize_alpaca_quote` return None on missing timestamp ✅
- P0.4: Parameterize `date.today()` in bootstrap ✅
- P0.5: Dead code — `normalize_reddit_mentions` removed ✅
- P0.6: Extract `_momentum_score` to shared function ✅
- P1.6: Update DESIGN.md for DuckDB-only state ✅
- P2.2: AlpacaConnector → extend BaseConnector ✅
- P2.3: Remove unused deps from pyproject.toml ✅

### P2.R (Resolved)
- P2.RA: Determinism & clock hygiene — bootstrap hash, I9 enforcement ✅
- P2.RB: CI & vault hygiene — vault gitignore, CUDA tooltips ✅
- P2.RC: Layout & documentation drift — DESIGN.md vs code vs ADR-0021 ✅
- P2.RD: Store port transaction boundary — atomic write for I1/I12 ✅
- P2.RE: Golden replay wire-up — rename stub, incremental DAG wiring ✅
- P2.RF: Normalize clock leak & data fabrication — `date.today()` in parsing ✅
- P2.RG: Atomic/incremental canonical writes — fix `_write_dataset` ✅
- P2.RH: Corporate-action modeling & split recovery ✅
- P2.RI: Timestamp hygiene — UTC everywhere, fix mixed naive/aware ✅
- P2.RJ: Earnings dataset in canonical store ✅
- P2.RK: Indicator validation against external reference ✅
- P2.RL: Validation gap heuristic — use trading calendar ✅
- P2.RM: Vault content-hash dedup instead of fetch_id ✅
- P2.RN: Insider transaction dedup key fix ✅
- P2.RO: Drop 50-day prune or document vault-replay rebuild ✅

### P3.R (Resolved — post-R1 through DOC-2)
- P0.2: Fix auto-commit in CanonicalStore ✅
- P0.3: Holiday-ignorant trading-day count in blackout ✅
- P0.4: Accrual ratio denominator fallback ✅
- P0.5: `max_gap_pct` configurable with sane default ✅
- P0.6: Scheduler crash — wrap `run_pipeline()` in try/except-finally ✅
- P0.7: Wire fill/risk/sizing config from config into pipeline ✅
- P0.8: Write pipeline core flow tests ✅ (`test_pipeline.py` exists at 855 lines)
- P1.1: Fix trailing stop — adjust stop price instead of full exit ✅
- P1.2: PaperPortfolio — handle drawdown_cut and daily_halt actions ✅
- P1.7: Fix architecture violation — `universe.py` decouple from ports ✅
- P1.8: Fix architecture violation — `ablation.py` decouple from Store ✅
- P1.13: AlpacaConnector — implement `daily_bars()` ✅
- P1.12: Implement `event_log.py` — EventLog abstraction ✅ (83 lines, exists and functional)
- P1.16: Fix `alpha-quant run` — wire actual pipeline call ✅
- P1.19: Module-level `_REGIME_CACHE` → instance-scoped ✅
- P2.10: Add partial fill simulation to fill model ✅
- P2.11: Implement Broker port (FakeBroker + AlpacaBroker) ✅
- P2.14: Breadth evaluation in bearish regime path ✅

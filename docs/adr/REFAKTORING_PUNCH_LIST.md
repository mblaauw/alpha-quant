# Refactoring Punch List — P5.7 Technical Refinement

## P0 — Must Fix Before Production

### P0.1: Fix `except ValueError, TypeError:` syntax bug (3 locations)
- **Files:** `alpha_quant/adapters/real/base_connector.py:39`, `alpha_quant/app/store.py:792,825`
- **Change:** `except ValueError, TypeError:` → `except (ValueError, TypeError):`
- **Effort:** 5 min, 2 files, 3 lines
- **Rationale:** Python 2 comma-separated syntax catches `ValueError` only; `TypeError` is bound to the variable name and **not caught**. Python 3.14 targets make this a real bug.

### P0.2: Fix auto-commit in CanonicalStore — transaction context broken
- **Files:** `alpha_quant/app/store.py`
- **Change:** Remove `self._state_conn.commit()` from every `save_*` method; let the caller manage commit via `transaction()` context manager
- **Effort:** 30 min, 1 file, ~20 lines
- **Rationale:** Every `save_*` calls `commit()` individually. The `transaction()` context manager issues `BEGIN TRANSACTION` but the first inner `save_*` immediately COMMITs it, breaking atomic grouping.

### P0.3: Fix holiday-ignorant trading-day count in blackout
- **Files:** `alpha_quant/domain/blackout.py`
- **Change:** In `_trading_days_before`, replace weekday-only back-count with `is_market_day()` from `calendar.py`
- **Effort:** 15 min, 1 file, ~5 lines
- **Rationale:** During holiday weeks, the function counts holidays as trading days, shortening the blackout window. Fails I7 determinism across different calendar years.

### P0.4: Fix accrual ratio denominator fallback
- **Files:** `alpha_quant/domain/fundamental.py`
- **Change:** Remove `total_debt + total_equity` fallback path in `_estimate_total_assets`. If `total_liabilities` is missing, skip the accrual check (return `passed_degraded=True`).
- **Effort:** 10 min, 1 file, ~3 lines
- **Rationale:** Debt is a subset of liabilities; using `debt + equity` understates total assets, which **overstates the accrual ratio**, causing false-positive fundamental failures.

### P0.5: Make `max_gap_pct` configurable with sane default
- **Files:** `alpha_quant/domain/fills.py`, `alpha_quant/app/config.py` (add FillConfig)
- **Change:** Move `max_gap_pct` from hardcoded constant to `FillConfig` model with default 0.005 (0.5%)
- **Effort:** 15 min, 2 files, ~10 lines
- **Rationale:** Current 0.2% threshold blocks most entries for volatile names. Not configurable — impossible to tune without code change.

### P0.6: Scheduler crash — wrap `run_pipeline()` in try/except-finally
- **Files:** `alpha_quant/app/scheduler.py`
- **Change:** Wrap `run_pipeline()` in `try/except Exception` with `store.complete_run(run_id, "failed")` in finally
- **Effort:** 10 min, 1 file, ~5 lines
- **Rationale:** If pipeline raises, run stays "running" forever. No recovery path.

### P0.7: Wire fill/risk/sizing config from config into pipeline
- **Files:** `alpha_quant/app/pipeline.py`, `alpha_quant/app/scheduler.py`
- **Change:** Extract `fill_config`, `risk_config`, `sizing_config` from `AppConfig` and pass to pipeline calls
- **Effort:** 15 min, 2 files, ~10 lines
- **Rationale:** Pipeline silently uses defaults instead of user-configured values. `fill_config` is accepted but never used in the pipeline body.

### P0.8: Write pipeline core flow tests
- **Files:** `tests/unit/test_pipeline.py` (new)
- **Change:** Test core pipeline flow with mocked adapters: bar loading, indicator state backfill, regime detection, risk exits, scoring/ranking/sizing, self-consistency check
- **Effort:** Medium (1 new file, ~200 lines)
- **Rationale:** 413-line file, the most critical file in the system, has zero test coverage.

## P1 — High Priority

### P1.1: Fix trailing stop — adjust stop price instead of full exit
- **Files:** `alpha_quant/domain/risk.py`, `alpha_quant/app/paper.py`
- **Change:** In `evaluate_stops`, emit trail_price adjustment action instead of full exit when trail conditions are met. In `paper.py`, implement trail price update on `Position.trail_price`. Make partial-take idempotent (track which thresholds have been hit).
- **Effort:** Medium (2 files, ~40 lines)
- **Rationale:** Current behavior fully exits on trail condition. The risk engine detects the trail correctly but `process_risk_actions` treats it as an exit. `trail_price` field on `Position` model exists but is dead code.

### P1.2: PaperPortfolio — handle drawdown_cut and daily_halt actions
- **Files:** `alpha_quant/app/paper.py`
- **Change:** Add handlers for `drawdown_cut` (reduce position by action ratio) and `daily_halt` (close all positions) in `process_risk_actions`
- **Effort:** Small (1 file, ~15 lines)
- **Rationale:** Currently produces `I10_unknown_risk_action` violations instead of acting. These are the primary risk controls.

### P1.3: Pipeline — call `write_halt()` when validation HALT occurs
- **Files:** `alpha_quant/app/pipeline.py`, `alpha_quant/app/scheduler.py`
- **Change:** After `validate_bars` returns HALT severity, call `write_halt()` with reason. In scheduler, check and propagate.
- **Effort:** 10 min, 2 files, ~5 lines
- **Rationale:** Halt detection exists but never creates the halt file. The feature is incomplete.

### P1.4: Wire LLM adapter in factory
- **Files:** `alpha_quant/app/factory.py`, `alpha_quant/app/config.py`
- **Change:** Add `create_llm(config, vault)` that returns `OpenAILikeLLM` or `CannedLLM` based on `config.data.mode`
- **Effort:** 10 min, 1 file, ~10 lines
- **Rationale:** `OpenAILikeLLM` exists with config and retry logic but is never wired into the DI container.

### P1.5: Wire Store adapter in factory
- **Files:** `alpha_quant/app/factory.py`
- **Change:** Add `create_store(config)` that returns `CanonicalStore` or `FixtureStore`
- **Effort:** 10 min, 1 file, ~8 lines
- **Rationale:** `CanonicalStore` implements all 19 Store methods but is never created by factory.

### P1.6: Wire EventSink adapter in factory
- **Files:** `alpha_quant/app/factory.py`
- **Change:** Add `create_event_sink(config)` that returns `SqliteEventSink` or `FakeEventSink`
- **Effort:** 10 min, 1 file, ~8 lines
- **Rationale:** `SqliteEventSink` fully implements the port but is never created by factory.

### P1.7: Fix architecture violation — `universe.py` decouple from ports
- **Files:** `alpha_quant/domain/universe.py`
- **Change:** Change `select()` to accept `list[Bar]` and `FundamentalsSnapshot | None` per symbol instead of port interfaces
- **Effort:** Medium (1 file, ~20 lines)
- **Rationale:** Domain module imports from `ports.market_data` and `ports.fundamentals`. Violates hexagonal architecture. Data fetching belongs in app layer.

### P1.8: Fix architecture violation — `ablation.py` decouple from Store
- **Files:** `alpha_quant/domain/ablation.py`
- **Change:** Remove `Store` port from `ShadowBook.__init__`. Accept `PortfolioSnapshot | None` and `list[Position]` directly. Persistence managed by caller.
- **Effort:** Medium (1 file, ~25 lines)
- **Rationale:** Domain module imports from `ports.store`. ShadowBook should be testable without a persistence layer.

### P1.9: Implement missing event emissions
- **Files:** `alpha_quant/app/pipeline.py`, `alpha_quant/domain/risk.py`, `alpha_quant/domain/validate.py`
- **Change:** Wire emissions for: `StalenessHaltSet`, `BookMarked`, `IndicatorStateUpdated`, `ErrorOccurred`, `ConsistencyViolation`, `DataQuarantined`, `DrawdownLadderTripped`, `RegimeChanged`
- **Effort:** Medium (3 files, ~40 lines)
- **Rationale:** 8 event types defined in `events.py` but never emitted anywhere. The audit trail is incomplete.

### P1.10: Graduate insider signal from binary to continuous
- **Files:** `alpha_quant/domain/insider_signal.py`
- **Change:** Score proportional to `total_value / market_cap` or number of distinct insiders. Add negative signal for sell-side clusters.
- **Effort:** Small (1 file, ~15 lines)
- **Rationale:** A $200K cluster scores the same as a $10M cluster. No sell-side analysis at all.

### P1.11: Add sector concentration check in ranking
- **Files:** `alpha_quant/domain/ranking.py`
- **Change:** Add `max_sector_exposure_pct` parameter. Cap candidates per sector proportionally to benchmark sector weight or use uniform allocation.
- **Effort:** Small (1 file, ~15 lines)
- **Rationale:** Top N candidates can all be from one sector. No diversification constraint.

### P1.12: Implement `event_log.py` — EventLog abstraction
- **Files:** `alpha_quant/domain/event_log.py` (new)
- **Change:** Create `EventLog` class with in-memory accumulator and batch write to store.
- **Effort:** Medium (1 file, ~50 lines)
- **Rationale:** `event_log.py` does not exist. Events are schema-only. No subscription mechanism, no batch writer, no in-memory accumulator. Events are only persisted via `store.save_event()`.

### P1.13: AlpacaConnector — implement `daily_bars()`
- **Files:** `alpha_quant/adapters/real/alpaca_connector.py`
- **Change:** Implement `daily_bars()` using `self.client.get_bars()` with date-range and symbol params
- **Effort:** Small (1 file, ~15 lines)
- **Rationale:** Primary MarketData method is abstract. Live mode with Alpaca raises `TypeError` on instantiation.

### P1.14: Fix RSI scoring — replace discrete ranges with continuous function
- **Files:** `alpha_quant/domain/technical.py`
- **Change:** Replace `if/elif` range-based RSI scoring with Gaussian centered at 50-55, penalizing both overbought (>80) and oversold (<30) extremes
- **Effort:** Small (1 file, ~10 lines)
- **Rationale:** RSI=80 scores 0.4 (same as RSI=40). Overlapping ranges create ambiguity. No penalization of extremes.

### P1.15: Add SPY benchmark to backtest metrics
- **Files:** `alpha_quant/app/backtest.py`
- **Change:** Use `compute_spy_buy_and_hold` from `ablation.py` to add `spy_return`, `spy_cagr`, `spy_max_dd` to `BacktestMetrics`
- **Effort:** 10 min, 1 file, ~5 lines
- **Rationale:** No benchmark comparison — can't tell if strategy beat SPY.

### P1.16: Fix `alpha-quant run` — wire actual pipeline call
- **Files:** `alpha_quant/cli.py`
- **Change:** Wire `cmd_run` to call `run_pipeline()` from `pipeline.py` instead of printing stub diagnostics
- **Effort:** Small (1 file, ~15 lines)
- **Rationale:** Currently creates adapters but never runs the pipeline. Essentially a no-op.

### P1.17: Implement CLI stubs — journal, report, backtest
- **Files:** `alpha_quant/cli.py`
- **Change:** Wire `cmd_journal` → `journal.generate_journal()`, `cmd_report` → `reporting.generate_weekly()/generate_monthly()`, `cmd_backtest` → `backtest.run()`
- **Effort:** Small (1 file, ~25 lines)
- **Rationale:** Three CLI commands print "not yet implemented" despite functional domain and app modules existing.

### P1.18: Integration/E2E tests for critical paths
- **Files:** `tests/integration/` (new files)
- **Change:** Store round-trip tests (DuckDB read/write), pipeline with fixture data, paper portfolio lifecycle, backtest metrics correctness
- **Effort:** Large (4-5 new files, ~300 lines)
- **Rationale:** `tests/integration/` is empty. No end-to-end tests exist.

### P1.19: Module-level `_REGIME_CACHE` → instance-scoped
- **Files:** `alpha_quant/app/pipeline.py`
- **Change:** Replace module-level `dict` with parameter passed through pipeline call chain
- **Effort:** 10 min, 1 file, ~5 lines
- **Rationale:** Global mutable state persists across runs, not thread-safe, leaks state between tests.

## P2 — Medium Priority

### P2.1: Add `vault_fetch_id` back-reference to canonical Parquet
- **Files:** `alpha_quant/app/store.py` (canonical schemas + write path)
- **Change:** Add `fetch_id` column to all canonical schemas; populate during write from connector metadata
- **Effort:** Medium (1 file, ~30 lines)
- **Rationale:** No way to trace a canonical bar back to the raw API response. Data lineage is broken.

### P2.2: Fix MentionCount field name inconsistency
- **Files:** `alpha_quant/app/store.py`, `alpha_quant/domain/models.py`
- **Change:** Either rename model field to `mention_date` or add explicit mapping doc
- **Effort:** 10 min, 2 files, ~3 lines
- **Rationale:** Model field `date` maps to Parquet column `mention_date`. Confusing for developers.

### P2.3: Add missing indexes on events table
- **Files:** `alpha_quant/app/store.py`
- **Change:** Add `CREATE INDEX idx_events_timestamp ON events(timestamp)` and `CREATE INDEX idx_events_type ON events(event_type)`
- **Effort:** 10 min, 1 file, ~3 lines
- **Rationale:** `load_events(since=...)` does full table scan. Acceptable at small scale but will degrade.

### P2.4: Implement atomic Parquet partition swap
- **Files:** `alpha_quant/app/store.py`
- **Change:** Write to temp directory within the same parent, then move atomically. Add `SELECT DISTINCT ON` on read to handle partial overlap.
- **Effort:** Medium (1 file, ~20 lines)
- **Rationale:** Three-step write (tmp → move → rm old) can leave both old and new partitions visible on crash.

### P2.5: Fix vault orphan file risk
- **Files:** `alpha_quant/app/vault.py`
- **Change:** Write compressed data to temp file, insert manifest, then rename temp to final path
- **Effort:** Small (1 file, ~10 lines)
- **Rationale:** Crash between `write_bytes` and manifest insert leaves orphan `.zst`.

### P2.6: Config versioning — add `config_version` field
- **Files:** `alpha_quant/app/config.py`, `config.toml`
- **Change:** Add `config_version: int = 1` field with validator. On mismatch, log migration path.
- **Effort:** Small (2 files, ~8 lines)
- **Rationale:** No schema evolution support. Schema changes produce confusing validation errors.

### P2.7: Volume-anomaly validation in `validate.py`
- **Files:** `alpha_quant/domain/validate.py`
- **Change:** Add volume spike (>10x prev day) and volume drop (<10% 20-day avg) checks at WARN severity
- **Effort:** Small (1 file, ~15 lines)
- **Rationale:** Volume anomalies can indicate data errors or corporate events. Currently undetected.

### P2.8: Make return spike threshold volatility-adjusted
- **Files:** `alpha_quant/domain/validate.py`
- **Change:** Replace `RETURN_SPIKE_PCT = 0.4` with `N * atr_pct` using per-symbol volatility
- **Effort:** Medium (1 file, ~20 lines)
- **Rationale:** 40% is too aggressive — flags legitimate events (biotech trial results). Should be volatility-adjusted.

### P2.9: Remove dead code — `trail_price`, `BacktestResult.decisions`
- **Files:** `alpha_quant/domain/models.py`, `alpha_quant/app/backtest.py`
- **Change:** Remove `trail_price` from Position model; remove `decisions` from BacktestResult
- **Effort:** 10 min, 2 files, ~5 lines
- **Rationale:** Both fields are defined but never written or read. Dead code.

### P2.10: Add partial fill simulation to fill model
- **Files:** `alpha_quant/domain/fills.py`
- **Change:** Add `max_fill_pct` parameter to simulate partial fills for large orders relative to ADV
- **Effort:** Small (1 file, ~10 lines)
- **Rationale:** Current model fills 100% or nothing. Real markets often have partial fills.

### P2.11: Implement Broker port (FakeBroker + AlpacaBroker)
- **Files:** `alpha_quant/adapters/fake/fake_broker.py` (new), `alpha_quant/adapters/real/alpaca_broker.py` (new), `alpha_quant/app/factory.py`
- **Change:** Implement both adapters. FakeBroker: in-memory order/position tracking. AlpacaBroker: via `alpaca-py` trading API.
- **Effort:** Large (2 new files, ~150 lines)
- **Rationale:** Broker port has zero implementations — no fake, no real. Dead code. Trading module must be uninstrumented (I13).

### P2.12: Add JSON config schema generation
- **Files:** `alpha_quant/app/config.py` (or new script)
- **Change:** Call `AppConfig.model_json_schema()` and write to `docs/config-schema.json`
- **Effort:** 10 min, 1 file, ~3 lines
- **Rationale:** Available via Pydantic but never used. Would auto-generate config documentation.

### P2.13: Make drawdown ladder rolling window instead of all-time peak
- **Files:** `alpha_quant/domain/risk.py`
- **Change:** Add `dd_window_days` config option. When set, measure drawdown from rolling window peak instead of all-time.
- **Effort:** Small (1 file, ~10 lines)
- **Rationale:** Default 15% from all-time peak shuts down new entries permanently after a single crash. Rolling window allows recovery.

### P2.14: Breadth evaluation in bearish regime path
- **Files:** `alpha_quant/domain/regime.py`
- **Change:** Move breadth check before the bearish exit — if breadth is very low and close < ema50, stay CAUTION instead of RISK_OFF
- **Effort:** 10 min, 1 file, ~3 lines
- **Rationale:** Breadth data is entirely ignored when market is in a bearish trend — may miss breadth-confirmed bear markets.

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

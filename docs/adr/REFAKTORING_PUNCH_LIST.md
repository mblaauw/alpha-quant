# Refactoring Punch List — P5.7 Technical Refinement

## P0 — Must Fix Before Production

### P0.1: Fix `except ValueError, TypeError:` syntax bug (3 locations)
- **Files:** `alpha_quant/domain/_normalize_helpers.py:15,40,68`
- **Change:** `except ValueError, TypeError:` → `except (ValueError, TypeError):`
- **Effort:** 5 min, 1 file, 3 lines
- **Rationale:** Python 2 comma-separated syntax catches `ValueError` only; `TypeError` is bound to the variable name and **not caught**. Python 3.14 targets make this a real bug. (Note: original locations in `base_connector.py` and `store/state.py` were already fixed; these three remain.)

## P1 — High Priority

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

## P2 — Medium Priority

### P2.1: Add `vault_fetch_id` back-reference to canonical Parquet
- **Files:** `alpha_quant/app/store/canonical.py`, `alpha_quant/app/store/schema.py` (canonical schemas + write path)
- **Change:** Add `fetch_id` column to all canonical schemas; populate during write from connector metadata
- **Effort:** Medium (1 file, ~30 lines)
- **Rationale:** No way to trace a canonical bar back to the raw API response. Data lineage is broken.

### P2.2: Fix MentionCount field name inconsistency
- **Files:** `alpha_quant/app/store/schema.py`, `alpha_quant/domain/models.py`
- **Change:** Either rename model field to `mention_date` or add explicit mapping doc
- **Effort:** 10 min, 2 files, ~3 lines
- **Rationale:** Model field `date` maps to Parquet column `mention_date`. Confusing for developers.

### P2.3: Add missing indexes on events table
- **Files:** `alpha_quant/app/store/state.py`
- **Change:** Add `CREATE INDEX idx_events_timestamp ON events(timestamp)` and `CREATE INDEX idx_events_type ON events(event_type)`
- **Effort:** 10 min, 1 file, ~3 lines
- **Rationale:** `load_events(since=...)` does full table scan. Acceptable at small scale but will degrade.

### P2.4: Implement atomic Parquet partition swap
- **Files:** `alpha_quant/app/store/state.py`
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
- **Change:** ADR-0015 (Incremental O(1) Indicator Engine) references a 50-day tail prune that was removed in P2.RO. Remove stale paragraph and cross-reference ADR-0027.
- **Effort:** 10 min, 1 file

### P3.8: Update ADR-0026 — correct content hash length from 8-char to 16-char
- **Change:** ADR-0026 describes an 8-char content hash; the implementation uses 16-char `sha256(source|endpoint|..)[:16]`. Update the ADR to match actual code.
- **Effort:** 5 min, 1 file

### P3.9: Update ADR-0021 — stale `app/store.py` path
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

# Refactoring Punch List — P4.R Post-Phase-4 Refinement Sprint

## P0 — Must Fix Before Next Production Run

### P0.1: Corporate action — stop_price not adjusted for splits/dividends
- **Files:** `src/domain/fills.py:145-169` (`apply_corporate_action`)
- **Issue:** After a 2:1 split, `stop_price` and `high_since_entry` on `Position` remain at pre-split levels. The stop is now double the correct level and will never be hit.
- **Fix:** After a split with ratio `R`, scale `stop_price /= R` and `high_since_entry /= R`. After a dividend, these fields don't need adjustment.
- **Effort:** Small (1 file, ~5 lines)
- **Rationale:** Bug — stops become ineffective after any corporate action; positions unwind via time-stops instead of risk-managed exits.

### P0.2: Gap-through protection threshold too tight (2%)
- **Files:** `src/domain/fills.py:20` (`FillConfig.max_gap_pct = 0.02`)
- **Issue:** The 2% max gap blocks all entries in volatile conditions. A 2.1% gap-up means no entries that day, and cascading misses during recovery days.
- **Fix:** Increase to `0.04` or make regime-adaptive (4% in RISK_ON, 2% in CAUTION, 1% in RISK_OFF).
- **Effort:** Small (1 file, ~3 lines)
- **Rationale:** Market recovery days with gap-ups are entirely missed.

### P0.3: Indicator key maps duplicated in 3 locations (must be single source of truth)
- **Files:** `src/alpha_quant/adapters/_parse.py:32-39`, `src/alpha_quant/domain/decision_context.py:115-122`
- **Issue:** `_OBSERVATION_KEY_MAP` in `_parse.py` and `_OBSERVATION_FIELD_MAP` in `decision_context.py` are byte-for-byte identical. Any change must be mirrored manually.
- **Fix:** Move the map to `src/alpha_quant/contracts/alpha_lake.py` as a module-level `INDICATOR_FIELD_MAP` and import in both locations. Add named fields to `TechnicalObservations` for each entry.
- **Effort:** Small (3 files, ~15 lines)
- **Rationale:** Adding a new indicator requires updating 3 files. Missing any one causes silent `None` returns.

## P1 — High Priority

### P1.1: Fix adapter → app import violation in llm_adapter.py (carried forward)
- **Files:** `src/adapters/real/llm_adapter.py:9`
- **Issue:** Adapter imports from `app.config`. Hard hexagonal architecture violation (runtime import).
- **Fix:** Move `LLMConfig` to a port-level type or create a config Protocol.
- **Effort:** Small (2 files, ~10 lines)
- **Carried forward from:** P1.1 (still unresolved)

### P1.2: `partial_taken` flag ownership — unclear who sets it
- **Files:** `src/domain/risk.py:114`, `src/app/pipeline_v2.py:371-396`
- **Issue:** `evaluate_stops()` checks `position.partial_taken` to prevent double partials, but doesn't return an updated position with the flag. The caller in `pipeline_v2.py` is responsible for saving with `partial_taken=True`. If this code path changes, double-partial takes silently occur.
- **Fix:** Either have `evaluate_stops()` return an updated `Position`, or document the contract explicitly.
- **Effort:** Small (1 file, ~5 lines or doc update)

### P1.3: `RiskAction` stored as `DomainEvent` — type mismatch
- **Files:** `src/app/pipeline_v2.py:674`
- **Issue:** `daily_halt_actions` returns `list[RiskAction]` but `events` is `list[DomainEvent]`. Currently suppressed with `# type: ignore`. Any consumer processing the events list (store serialization, dashboard) will crash or silently drop these items.
- **Fix:** Create a `DailyHaltTriggered` DomainEvent subclass and convert RiskAction to it.
- **Effort:** Small (2 files, ~15 lines)

### P1.4: `symbol_adv` tiebreaker never passed to ranking
- **Files:** `src/app/pipeline_v2.py:551`, `src/domain/ranking.py:40`
- **Issue:** The `rank()` function has a `symbol_adv` parameter for ADV-based tiebreaking, but `pipeline_v2.py` never passes it. Candidates with equal composite scores are ordered arbitrarily.
- **Fix:** Gather ADV data from the neutral observations (via `TechnicalObservations.volume_ratio_21`) or add ADV to the neutral observation contract.
- **Effort:** Small (1 file, ~5 lines)

### P1.5: Legacy parse functions duplicated in both adapters
- **Files:** `src/alpha_quant/adapters/real/alpha_lake_rest.py:192-259`, `src/alpha_quant/adapters/fake/alpha_lake_http_fixture.py:177-244`
- **Issue:** Six `_legacy_parse_*` functions and `_legacy_panel` are duplicated identically. Bug fix or schema update requires touching both files.
- **Fix:** Extract to `_parse.py` alongside the observation parsers, or delete legacy code paths entirely (move fully to `NeutralObservations`).
- **Effort:** Medium (2 files, ~100 lines consolidated)

### P1.6: `Regime` type and `REGIME_MULTIPLIERS` defined in 3 places
- **Files:** `src/domain/regime.py:7-11`, `src/alpha_quant/domain/policy/regime_policy.py:9-13`, `src/app/pipeline_v2.py:92-96`
- **Issue:** Three separate definitions of the same type and multiplier dict. Drift would cause silent divergence.
- **Fix:** Remove duplicates from `regime_policy.py` (import from `domain/regime.py`) and from `pipeline_v2.py` (import from canonical location).
- **Effort:** Small (2 files, ~10 lines)

### P1.7: `parse_date()` silent `date.today()` fallback in adapter layer
- **Files:** `src/alpha_quant/adapters/_parse.py:25`
- **Issue:** When date parsing fails, returns `date.today()` instead of raising. Violates the "no `date.today()` in domain" rule.
- **Fix:** Raise `ValueError` instead; let caller handle parse failures explicitly.
- **Effort:** Small (1 file, ~2 lines)

### P1.8: No tests for any of the 7 policy modules
- **Files:** `tests/unit/` — zero files for `technical_policy`, `regime_policy`, `fundamental_policy`, `insider_policy`, `attention_policy`, `earnings_blackout_policy`, `composite_policy`
- **Issue:** The complete decision policy layer has zero test coverage. All 7 modules are pure functions — trivial to unit test.
- **Effort:** Medium (7 files, ~150 lines)
- **Rationale:** Policy logic is the core value of the system; untested policy logic is the highest-risk gap.

## P2 — Medium Priority

### P2.1: `AttentionPolicy` uses `statistics.mean/stdev` — overkill for small lists
- **Files:** `src/alpha_quant/domain/policy/attention_policy.py`
- **Issue:** Uses stdlib `statistics` module for 2-30 element lists. Consistent with correctness but inconsistent with rest of codebase (manual `max/min` patterns).
- **Effort:** Trivial (1 file, ~5 lines)

### P2.2: Negative notional floor applied after cap check
- **Files:** `src/domain/sizing.py:49`
- **Issue:** `notional = max(notional, 0.0)` is applied after the min-with-max cap, not before. Not exploitable (all inputs validated earlier) but ordering is fragile.
- **Effort:** Trivial (1 file, ~2 lines)

### P2.3: `sector=None` bypasses sector diversification caps
- **Files:** `src/domain/ranking.py:52`
- **Issue:** When `sector_map` returns `None` for a symbol, the sector-diversification count is neither incremented nor checked. Unclassified symbols fill slots freely.
- **Effort:** Small (1 file, ~5 lines)

### P2.4: Price-trend double-counting in composite score
- **Files:** `src/alpha_quant/domain/policy/composite_policy.py`, `src/alpha_quant/domain/policy/technical_policy.py`
- **Issue:** `technical_score` uses MA50 ratio (trend, 0.3125 weight); `momentum_score` uses 63-day return (0.25 weight). Combined ~55% weight on price direction. By design but worth tuning via ablation.
- **Effort:** Research (requires ablation analysis)

### P2.5: `BarObservation` ↔ `Bar` bridge adapter exists in pipeline
- **Files:** `src/app/pipeline_v2.py:109-119` (`_make_bar`)
- **Issue:** Necessary abstraction but adds maintenance surface. Will be eliminated when `src/domain/models.py` is migrated to `src/alpha_quant/contracts/`.
- **Effort:** Blocked on Phase 5 migration

### P2.6: `_get_technical_field` silent fallthrough path
- **Files:** `src/alpha_quant/domain/decision_context.py:131-136`
- **Issue:** If a key exists in the map but the field is misspelled in the dataclass, `getattr(..., None)` returns `None` silently.
- **Effort:** Small (1 file, ~3 lines — add a check)

### P2.7: Earnings blackout is forward-only — yesterday's earnings not blocked
- **Files:** `src/alpha_quant/domain/policy/earnings_blackout_policy.py:24`
- **Issue:** Only checks `today <= event_date <= window_end`. Earnings announced yesterday are not covered. By design but worth documenting.
- **Effort:** Small (1 file, ~3 lines)

### P2.8: Legacy DuckDB state files still active — 9 files, ~40+ references
- **Files:** `src/app/store/*.py` (7 files), `src/app/dashboard.py`, `src/adapters/real/event_sink.py`
- **Issue:** Production system has two parallel state stores (DuckDB legacy + PostgreSQL new). The DuckDB path is the active runtime path; PostgreSQL is only used by CLI commands.
- **Fix:** Complete the DuckDB → PostgreSQL migration and delete the legacy store files.
- **Effort:** Large (blocked on Phase 3+ pipeline integration)
- **Dependency:** Blocked on `streamlit + pandas + duckdb` cleanup

### P2.9: Streamlit dashboard still the only operator surface
- **Files:** `src/app/dashboard.py`
- **Issue:** Streamlit depends on DuckDB. Cannot remove either dependency until FastAPI dashboard exists.
- **Fix:** Implement Phase 6 (FastAPI dashboard)
- **Effort:** Large (Phase 6 scope)

### P2.10: `alpha_quant/__init__.py` empty
- **Files:** `src/alpha_quant/__init__.py`
- **Issue:** Package init exists but doesn't export anything. Consumers must know deep import paths.
- **Fix:** Add `__all__` with public API exports after Phase 5 migration settles.
- **Effort:** Small (1 file, ~20 lines)

## P3 — Documentation & ADRs

### P3.1: Create ADR-0037 — PostgreSQL Operational System of Record
- **Status:** Done (created during P4.R)

### P3.2: Create ADR-0038 — Append-Only Ledger with Rebuildable Projections
- **Status:** Done (created during P4.R)

### P3.3: Create ADR-0039 — S3-Compatible Artifact Store
- **Status:** Done (created during P4.R)

### P3.4: Create ADR-0040 — Database-Backed Halts and Transactional Run Locks
- **Status:** Done (created during P4.R)

### P3.5: Create ADR-0041 — Migration Strategy to `src/alpha_quant/`
- **Status:** Done (created during P4.R)

### P3.6: Update ADR README index — correct statuses for ADR-0032/0034
- **Status:** Done (updated during P4.R)

### P3.7: Prefix indicator maps with `INDICATOR_FIELD_MAP` in contracts module
- **Status:** Done (fixed during P4.R)

## Completed Items (from previous refinements, preserved for audit trail)

### Resolved During Phase 4
- P0.1: `except ValueError, TypeError:` syntax bug — fixed with `# fmt: skip` ✅
- P0.2: Composite score formula inconsistency — consolidated in `composite_policy.py` ✅
- P0.3: Indicator key maps duplicated — moved to single source of truth in contracts ✅

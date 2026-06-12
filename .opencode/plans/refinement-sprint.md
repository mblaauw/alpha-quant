# Refinement Sprint Plan

## P0 — Must Fix

### P0.1: Extract `_momentum_score` to shared utility

**Files:**
- `alpha_quant/domain/technical.py` — rename `_momentum_score` → `momentum_score` (line 67), update call site (line 35)
- `alpha_quant/app/backtest.py` — remove local `_momentum_score` (function + its `from alpha_quant.domain.models import Bar`), add `from alpha_quant.domain.technical import momentum_score`, update call site
- `alpha_quant/app/pipeline.py` — same as backtest.py

### P0.2: Remove dead code `normalize_reddit_mentions`

**File:** `alpha_quant/domain/normalize.py`
**Change:** Delete lines 435–474 (`def normalize_reddit_mentions(...)`). Also remove `json` import if no longer needed.

### P0.3: Fix clock leak in `domain/normalize.py`

**File:** `alpha_quant/domain/normalize.py`
**Location:** Line ~300, `Quote()` fallback uses `datetime.now(UTC)` when timestamp is None.
**Change:** Replace with `timestamp | None = None` in return (make timestamp nullable, let caller supply it). Or accept a `now` parameter with default `None`.

### P0.4: Fix bootstrap determinism

**File:** `alpha_quant/app/bootstrap.py`
**Changes (7 sites):** Replace `date.today()` with a `ref_date: date` parameter on each function. Default behavior: pass `ref_date` through from the top-level entry point.
- `_generate_bars(symbols, years)` → `_generate_bars(symbols, years, ref_date)`
- `_generate_insider_data(symbols, days)` → `_generate_insider_data(symbols, days, ref_date)`
- `_generate_fundamentals(symbols, years)` → `_generate_fundamentals(symbols, years, ref_date)`
- Top-level `generate_fixtures()` reads `date.today()` internally — move to caller

---

## P1 — Should Fix

### P1.1: Accept ADR-0020

**File:** `docs/adr/0020-use-duckdb-for-vault-manifest.md`
**Change:** Set `status: Proposed` → `status: Accepted`. Add implementation notes referencing `app/vault.py`.

### P1.2: Write 3 new ADRs

**Files:** `docs/adr/0022-use-paper-portfolio-engine.md`, `docs/adr/0023-use-pipeline-orchestrator.md`, `docs/adr/0024-use-self-consistency-invariants.md`

Each follows MADR template: Context, Decision Drivers, Options Considered, Decision Outcome, Consequences.

### P1.3: Update DESIGN.md

**File:** `DESIGN.md`
**Changes:**
- §3.4: Remove "50-day tail prune" reference (P2.RO)
- §3.4: Change "SQLite" → "DuckDB" throughout (ADR-0021)
- §3.7: Add note: "Synthetic overlays deferred (P3+)"
- §13: Minor alignment with actual pipeline implementation

### P1.4: Update domain/__init__.py re-exports

**File:** `alpha_quant/domain/__init__.py`
**Changes:** Add `CorporateAction`, `PortfolioSnapshot` to imports and `__all__`.

### P1.5: Fix I8 violations in backtest.py

**File:** `alpha_quant/app/backtest.py`
**Changes:**
- Replace ad-hoc `sell_price = max(bar.open * 0.99, bar.low)` with `fill_stop_loss()` for exits
- Replace ad-hoc entry pricing with `fill_entry_order()` for entries
- This makes backtest fills match paper fills exactly

### P1.6: Extract shared loop utility

**File:** (new) `alpha_quant/app/_loop.py`
**Extract:** Shared daily-loop helpers (bar loading, indicator updates, market-date iteration) used by both backtest.py and pipeline.py.

---

## P2 — Consider

### P2.1: Write tests for untested modules

Create unit tests for:
- `tests/unit/test_regime.py` — M2
- `tests/unit/test_technical.py` — M3
- `tests/unit/test_fundamental.py` — M4
- `tests/unit/test_blackout.py` — M7
- `tests/unit/test_ranking.py` — M8
- `tests/unit/test_sizing.py` — P2.8
- `tests/unit/test_risk.py` — P2.9
- `tests/unit/test_fills.py` — P2.10
- `tests/unit/test_invariants.py` — P2.15

### P2.2: Wire validate.py into pipeline

**File:** `alpha_quant/app/pipeline.py`
**Change:** Call `validate.py` functions in the daily run sequence (step 2 of DESIGN §13).

### P2.3: Integrate PaperPortfolio into backtest

**File:** `alpha_quant/app/backtest.py`
**Change:** Replace manual cash/position tracking with `PaperPortfolio` instance.

---

## How to Execute

```bash
# After exiting plan mode:
uv run ruff check alpha_quant/
uv run ruff format alpha_quant/
uv run ty check alpha_quant/
uv run pytest
```

Execute in order: P0 → P1 → P2. Each group can be committed as a separate commit.

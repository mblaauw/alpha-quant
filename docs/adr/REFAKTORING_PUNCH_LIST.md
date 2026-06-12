# Refactoring Punch List — P1.R Technical Refinement

## P0 — Must Fix (blocks P1.8)

### P0.1: Make `parse()` concrete in BaseConnector
- **Files:** `alpha_quant/adapters/real/base_connector.py`
- **Change:** Remove `@abstractmethod` from `parse()`, provide default `return data`
- **Then remove overrides in:** `eodhd_connector.py`, `openinsider_connector.py`, `reddit_sentiment_connector.py`
- **Effort:** 5 min, 3 files, ~6 lines removed
- **Rationale:** 3 subclasses have byte-for-byte identical stub — indicates the method should not be abstract

### P0.2: Extract `_parse_bar()` helper in EODHDConnector
- **Files:** `alpha_quant/adapters/real/eodhd_connector.py`
- **Change:** Extract shared bar-construction logic from `daily_bars()` and `bulk_last_day()` into a `_parse_bar(entry, symbol)` helper
- **Effort:** 10 min, 1 file, ~14 lines consolidated
- **Rationale:** 16 near-identical lines duplicated — only `symbol` differs

### P0.3: Make `normalize_alpaca_quote` return None on missing timestamp
- **File:** `alpha_quant/domain/normalize.py`
- **Status:** ✅ Completed in refinement sprint 2026-06-12
- **Change:** Removed `datetime.now(UTC)` fallback when timestamp is None — returns None instead, letting caller decide

### P0.4: Parameterize `date.today()` in bootstrap
- **File:** `alpha_quant/app/bootstrap.py`
- **Status:** ✅ Completed in refinement sprint 2026-06-12
- **Change:** Added `ref_date` parameter to all `_generate_*` functions and `run_bootstrap`, making fixtures deterministic

### P0.5: Dead code — `normalize_reddit_mentions` never called
- **File:** `alpha_quant/domain/normalize.py`
- **Status:** ✅ Completed in refinement sprint 2026-06-12
- **Change:** Deleted the function and its unused `_COMMON_WORDS` lookup table (63 lines removed)

### P0.6: Extract `_momentum_score` to shared function
- **File:** `alpha_quant/domain/technical.py`, `app/backtest.py`, `app/pipeline.py`
- **Status:** ✅ Completed in refinement sprint 2026-06-12
- **Change:** Renamed `_momentum_score` → `momentum_score` in technical.py, removed duplicated copies from backtest.py and pipeline.py

## P1 — Should Fix (before P1.9)

### P1.1: Remove redundant `TYPE_CHECKING` + `Vault` imports from subclasses
- **Files:** `eodhd_connector.py`, `sec_connector.py`, `openinsider_connector.py`, `reddit_sentiment_connector.py`
- **Change:** Delete the `TYPE_CHECKING` guard + `Vault` import block from each subclass (BaseConnector already carries the type)
- **Effort:** 5 min, 4 files, ~12 lines removed
- **Rationale:** All four subclasses re-import `Vault` under `TYPE_CHECKING`, but the parent already does — the type flows through `super().__init__()`

### P1.2: Promote `_parse_date()` to shared utility
- **Files:** `base_connector.py` (add), `eodhd_connector.py` + `openinsider_connector.py` (remove local versions)
- **Change:** Add `_parse_date(value: str | None, formats: tuple[str, ...] = ...)` to BaseConnector (or a new `_utils.py`). Replace duplicate implementations.
- **Effort:** 10 min, 3 files, ~8 lines consolidated
- **Rationale:** Same algorithm (iterate format strings, catch exceptions, return `date | None`) implemented twice with slightly different format lists

### P1.3: Extract `_expect_type()` guard helper
- **Files:** `eodhd_connector.py`
- **Change:** Create `_expect_type(raw: Any, expected: type, *, source: str, description: str) -> None` that raises `DataNormalizationError` with consistent `raw=str(...)[:500]` truncation
- **Effort:** 5 min, 1 file, ~8 lines consolidated
- **Rationale:** The `if not isinstance(...): raise DataNormalizationError(...)` pattern with identical truncation appears 4 times

### P1.4: Fix I8 violation — backtest fill model
- **Status:** New — issue #132
- **Change:** Use `fill_stop_loss()` and `fill_entry_order()` in backtest.py instead of ad-hoc pricing

### P1.5: Extract shared loop utilities
- **Status:** New — issue #133
- **Change:** Extract bar-loading, date-iteration, and scoring conductor helpers shared by backtest.py and pipeline.py

### P1.6: Update DESIGN.md for DuckDB-only state
- **Status:** ✅ Completed in refinement sprint 2026-06-12
- **Change:** Updated §3.4, §9.1, §9.3 to reference DuckDB (via Store port) instead of SQLite; removed 50-day prune reference; noted synthetic overlays deferred

## P2 — Consider (post-P1 milestone)

### P2.1: Connector constructor pass-through → config dataclass
- **Files:** All connector constructors
- **Change:** Create a `ConnectorSettings` dataclass (or reuse existing `ConnectorConfig` from `config.py`) for the repeated `user_agent`, `tokens_per_second`, `max_burst`, `timeout_s` pass-through
- **Effort:** 15 min, 5 files
- **Rationale:** Every subclass constructor accepts and forwards the same 4 parameters

### P2.2: AlpacaConnector → extend BaseConnector for HTTP parts
- **Files:** `alpaca_connector.py`, `base_connector.py`
- **Status:** ✅ Completed — AlpacaConnector now extends BaseConnector (was already done before refinement sprint)
- **Change:** Make `trading_calendar()` use `BaseConnector.fetch()` for its HTTP call (adding rate limiting, retry, vault, logging). Keep SDK-based methods (`latest_quote`, `latest_bar`) as-is.

### P2.3: Remove unused deps from pyproject.toml
- **Status:** ✅ Already done — polars, apscheduler, sqlalchemy already removed from pyproject.toml

### P2.4: Write tests for untested modules
- **Status:** New — issue #134
- **Effort:** Large (9 new test files, ~500 lines)
- **Rationale:** Only 14% domain module coverage; no tests for M2-M8, sizing, risk, fills, invariants

### P2.5: Wire validate.py into pipeline
- **Status:** New — issue #135
- **Effort:** Small (1 file, ~20 lines)
- **Rationale:** Pipeline skips step 2 of DESIGN §13 — no gap/staleness detection

### P2.6: Integrate PaperPortfolio into backtest
- **Files:** `app/backtest.py`, `app/paper.py`
- **Change:** Use PaperPortfolio for cash/position tracking instead of manual dicts
- **Effort:** Medium (1 file, ~50 lines changed)
- **Rationale:** Eliminates duplicate state management logic

### P2.7: Deprecate `numpy` in favor of DuckDB SQL for indicator math (P1.10)
- **Files:** `pyproject.toml`
- **Change:** After P1.10 analysis, if DuckDB SQL window functions can replace numpy recurrences, remove numpy dep
- **Effort:** Evaluation during P1.10
- **Rationale:** ADR-0008 chose numpy recurrences, but DuckDB can express EMA/RSI/ATR as SQL window functions — evaluate both approaches during P1.10 implementation

## Current Dependency Audit Summary

| Dependency | P1 Usage | Verdict |
|---|---|---|
| `httpx>=0.28` | base_connector, alpaca_connector | **Keep** |
| `pydantic>=2.10` | domain/models, events, config | **Keep** |
| `pydantic-settings>=2.7` | app/config | **Keep** |
| `structlog>=24.4` | 7 files | **Keep** |
| `tenacity>=9.0` | base_connector | **Keep** |
| `zstandard>=0.23` | vault | **Keep** |
| `selectolax>=0.3` | openinsider_connector | **Keep** |
| `duckdb>=1.2` | vault, canonical store | **Keep** |
| `pyarrow>=19.0` | fixtures, canonical store | **Keep** |
| `alpaca-py>=0.30` | alpaca_connector | **Keep** |
| `numpy>=2.2` | derive, backtest, pipeline | **Keep** (broader usage than P1) |
| `hypothesis>=6.0` (dev) | 0 files | **Keep or use** — installed but never imported |

## New Library Recommendations

| Library | Reason | Decision |
|---|---|---|
| `fsspec` | Filesystem abstraction for cloud vault (S3/GCS) | **Defer** — not needed until cloud deployment |
| `msgpack` | Smaller/faster binary serialization | **Defer** — vault JSON is adequate for P1 |
| `click` / `typer` | Richer CLI framework | **Skip** — argparse is sufficient for 9 subcommands (per ADR-0004) |
| `pydantic-ai` | SDK for LLM integration | **Skip** — raw httpx is simpler for one POST call (per ADR-0011) |
| `schedule` | Simple cron-like scheduler | **Skip** — apscheduler is richer; if not needed, use system cron |
| `backoff` | Retry decorator | **Skip** — tenacity is already used and equivalent |
| `httpx-cache` | HTTP response caching | **Defer** — SEC's custom SQLite cache is adequate for its unique use case |

## Architectural Consistency Findings

1. **AlpacaConnector** — ✅ Now extends BaseConnector (was listed as P2.2, already resolved)
2. **SECConnector SQLite cache** — unique to SEC, no need to generalize; the 1 req/sec rate limit makes caching necessary and the TTL-based refresh is clean
3. **Vault interface** — `store(source, endpoint, params, data_bytes, ingest_ts)` is consistent across all callers; no friction found
4. **DuckDB dual use** — vault manifest (OLTP inserts) + future analytical queries (OLAP reads) — documented in ADR-0020 (now Accepted)
5. **I8 partial violation** — backtest.py doesn't use fill model (issue #132)
6. **~40% code duplication** — between backtest.py and pipeline.py (issue #133)
7. **Test coverage gap** — 14% domain module coverage (issue #134)

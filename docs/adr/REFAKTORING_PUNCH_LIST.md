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

## P2 — Consider (post-P1 milestone)

### P2.1: Connector constructor pass-through → config dataclass
- **Files:** All connector constructors
- **Change:** Create a `ConnectorSettings` dataclass (or reuse existing `ConnectorConfig` from `config.py`) for the repeated `user_agent`, `tokens_per_second`, `max_burst`, `timeout_s` pass-through
- **Effort:** 15 min, 5 files
- **Rationale:** Every subclass constructor accepts and forwards the same 4 parameters

### P2.2: AlpacaConnector → extend BaseConnector for HTTP parts
- **Files:** `alpaca_connector.py`, `base_connector.py`
- **Change:** Make `trading_calendar()` use `BaseConnector.fetch()` for its HTTP call (adding rate limiting, retry, vault, logging). Keep SDK-based methods (`latest_quote`, `latest_bar`) as-is.
- **Effort:** 30 min, 2 files
- **Rationale:** `trading_calendar()` creates a temporary `httpx.Client()` with no timeout, no retry, no rate limiting, no vault — architectural inconsistency

### P2.3: Remove unused deps from pyproject.toml
- **Files:** `pyproject.toml`
- **Change:** Remove `polars`, `apscheduler`, `sqlalchemy` (add back when P1.9+ / P2 needs them). Leave `numpy` (needed for P1.10).
- **Effort:** 2 min
- **Rationale:** These deps are not imported anywhere in P1 code — they add lockfile weight and audit surface with zero benefit

### P2.4: Deprecate `numpy` in favor of DuckDB SQL for indicator math (P1.10)
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
| `duckdb>=1.2` | vault | **Keep** |
| `pyarrow>=19.0` | fixtures | **Keep** |
| `alpaca-py>=0.30` | alpaca_connector | **Keep** |
| `numpy>=2.2` | 0 files | **Keep** (needed for P1.10) |
| `polars>=1.20` | 0 files | **Remove** (unused; add back for P1.9+) |
| `apscheduler>=3.10` | 0 files | **Remove** (unused; add back for P2 schedule) |
| `sqlalchemy>=2.0` | 0 files | **Remove** (unused; add back for P2+ state store) |

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

1. **AlpacaConnector** — does not extend BaseConnector (P2.2 above)
2. **SECConnector SQLite cache** — unique to SEC, no need to generalize; the 1 req/sec rate limit makes caching necessary and the TTL-based refresh is clean
3. **Vault interface** — `store(source, endpoint, params, data_bytes, ingest_ts)` is consistent across all callers; no friction found
4. **DuckDB dual use** — vault manifest (OLTP inserts) + future analytical queries (OLAP reads) — warrants ADR-0020

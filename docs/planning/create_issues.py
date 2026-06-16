#!/usr/bin/env python3
"""Create GitHub issues from BACKLOG.md for alpha-quant."""

import subprocess
import sys

REPO = "mblaauw/alpha-quant"

ISSUES = [
    # ── Epic 0: Foundation & Skeleton ──
    {
        "title": "P0.1: Project scaffold + CLI entrypoint",
        "body": """## Description

Create the `src/` layout with hexagon packages (`domain/`, `app/`, `adapters/`, `ports/`), `pyproject.toml` with all dependencies, and a `cli.py` entrypoint with 9 subcommand stubs: `run`, `replay`, `backtest`, `bootstrap`, `journal`, `ask`, `report`, `status`, `halt`.

## Acceptance Criteria

- [ ] `pip install -e .` installs the package
- [ ] `alpha-quant --help` shows all 9 subcommands
- [ ] Each subcommand prints a stub message and exits 0
- [ ] `ruff check .` passes with zero warnings
- [ ] `ty check src/` passes
- [ ] Directory structure matches DESIGN §1 exactly: `src/domain/`, `src/ports/`, `data/connectors/`, `src/adapters/real/`, `src/adapters/fake/`, `src/app/`, `fixtures/`

## Technical Details

- Use `pyproject.toml` with `[project.scripts]` entry point: `alpha-quant = "app.cli:main"`
- CLI: `argparse` (stdlib) — no Click/Typer for v1
- Dependencies: httpx, pydantic, pydantic-settings, structlog, sqlalchemy, duckdb, pyarrow, polars, numpy, tenacity, apscheduler, zstandard, selectolax
- Dev deps: pytest, pytest-cov, hypothesis, mypy, ruff""",
        "labels": ["story", "priority/p0", "size/l:5", "domain/backend", "P0"],
    },
    {
        "title": "P0.2: Port interfaces — Clock, Store, EventSink, LLM, MarketData, Fundamentals, InsiderFeed, SentimentFeed, Broker",
        "body": """## Description

Define all port interfaces (abstract base classes) in `src/ports/`. These are the contracts that adapters implement and domain code depends on. The Broker port is defined but raises `NotImplementedError`.

## Acceptance Criteria

- [ ] `Clock` port: `now()`, `today()`, `market_date()` methods
- [ ] `MarketData` port: `daily_bars()` , `latest_quote()`, `trading_calendar()`
- [ ] `Fundamentals` port: `snapshot()`, `earnings_calendar()`
- [ ] `InsiderFeed` port: `cluster_transactions()`, `recent_clusters()`
- [ ] `SentimentFeed` port: `mention_counts()`, `baseline()`
- [ ] `Store` port: CRUD for bars, decisions, orders, fills, positions, events, indicator_state
- [ ] `EventSink` port: `emit(event: DomainEvent)`
- [ ] `LLM` port: `explain()`, `generate_card()`
- [ ] `Broker` port: defined, raises NotImplementedError at runtime
- [ ] All return types are frozen pydantic models
- [ ] No import from `adapters/` or `data/` — enforced by import linter

## Technical Details

- Use `abc.ABC` + `@abstractmethod`
- DomainEvent is a pydantic discriminated union
- All outputs are pydantic `BaseModel` with `frozen=True`""",
        "labels": ["story", "priority/p0", "size/xl:8", "domain/backend", "P0"],
    },
    {
        "title": "P0.3: Configuration system (TOML + pydantic-settings)",
        "body": """## Description

Implement config loading from `config.toml` using pydantic-settings with env var overrides. Schema matches DESIGN §2 exactly.

## Acceptance Criteria

- [ ] `--config path/to/config.toml` loads custom config
- [ ] Default config discovered in `$PWD/config.toml` and `~/.alpha-quant/config.toml`
- [ ] Every field overridable via env var: `ALPHA_QUANT_PAPER__STARTING_EQUITY=50000`
- [ ] Config model validates numeric bounds
- [ ] `status --config` prints resolved config (secrets redacted)
- [ ] Invalid config raises clear startup error with file + line + field

## Technical Details

- `pydantic-settings` `BaseSettings` with `env_prefix="ALPHA_QUANT_"`, `env_nested_delimiter="__"`
- Secret fields use `pydantic.SecretStr`""",
        "labels": ["story", "priority/p0", "size/xs:1", "domain/backend", "P0"],
    },
    {
        "title": "P0.4: Event log system",
        "body": """## Description

Implement append-only typed event log. All event types from DESIGN §10 as pydantic discriminated union. Events emitted by every pipeline stage.

## Acceptance Criteria

- [ ] All 20+ event types implemented as frozen dataclasses
- [ ] Events carry: `event_type`, `timestamp`, `run_id`, `payload`, `source`
- [ ] `EventSink.emit()` writes to both SQLite and structlog JSON stream
- [ ] SQLite schema: `CREATE TABLE events (id TEXT PK, run_id TEXT, event_type TEXT, ts TEXT, payload_json TEXT, source TEXT)`
- [ ] Events queryable by `run_id`, `event_type`, date range
- [ ] Event emission ≤1ms per event (benchmark test)

## Technical Details

- Pydantic discriminated union for type safety
- structlog: `structlog.get_logger().info("domain_event", event=event.model_dump_json())`
- SQLite batch insert every 100ms or per stage""",
        "labels": ["story", "priority/p0", "size/s:2", "domain/backend", "P0"],
    },
    {
        "title": "P0.5: Clock virtualization — SystemClock + VirtualClock",
        "body": """## Description

Implement `SystemClock` (wraps datetime + market calendar) and `VirtualClock` (incrementable for replay). Nothing reads OS clock directly.

## Acceptance Criteria

- [ ] `SystemClock.now()` returns real UTC time
- [ ] `SystemClock.market_date()` returns last trading day
- [ ] `VirtualClock` constructed with start_date, advances by day
- [ ] VirtualClock skips weekends and holidays
- [ ] No code outside clock adapters calls `datetime.now()` — enforced by CI grep

## Technical Details

- Minimal static NYSE holiday list in code
- `VirtualClock._current_date` advances via `+= timedelta(days=1)`, skips non-market days""",
        "labels": ["story", "priority/p0", "size/xs:1", "domain/backend", "P0"],
    },
    {
        "title": "P0.6: Fake adapters for all ports",
        "body": """## Description

Implement fixture-backed fake adapters for every port: FixtureMarketData, FixtureFundamentals, FixtureInsiderFeed, FixtureSentimentFeed, FixtureStore, CannedLLM. Read from fixture bundle deterministically.

## Acceptance Criteria

- [ ] Each fake adapter implements the same port interface as real twin
- [ ] FixtureMarketData returns data from fixture parquet for symbol/date range
- [ ] CannedLLM returns deterministic template strings (no network calls)
- [ ] Fake adapters never make network calls, never read OS clock
- [ ] Clear errors when fixture data missing for unknown symbol

## Technical Details

- Fixture bundle: `fixtures/v1/` with `bars/`, `fundamentals/`, `insider_tx/`, `mentions/`, `indicator_state.parquet`, `manifest.json`
- FixtureMarketData reads parquet via DuckDB""",
        "labels": ["story", "priority/p0", "size/s:2", "domain/backend", "P0"],
    },
    {
        "title": "P0.7: Bootstrap command + fixture bundle generator",
        "body": """## Description

Implement `alpha-quant bootstrap` that reads bootstrap config, fetches history for 50 symbols + benchmarks, writes vault → canonical → seeds indicator_state → freezes fixture bundle.

## Acceptance Criteria

- [ ] Bootstrap processes exactly the requested symbols from config
- [ ] Fetches: history_years of daily bars, fundamentals, earnings calendar, OpenInsider history
- [ ] Writes vault (zstd) → canonical (parquet + SQLite) → indicator_state
- [ ] `--fixture-only` freezes fixture bundle with manifest.json + content hashes
- [ ] Re-running with same data is idempotent (content-addressed vault)
- [ ] Default 50-symbol list includes diversity per DESIGN §3.7

## Technical Details

- Content-addressed: `fetch_id = sha256(source|endpoint|params|ingest_ts)[:16]`
- Vault path: `vault/{source}/{yyyy}/{mm}/{dd}/{fetch_id}.zst`
- Manifest in DuckDB: `manifest.duckdb`
- Synthetic overlays applied on fixture copy only""",
        "labels": ["story", "priority/p0", "size/m:3", "domain/backend", "P0"],
    },
    {
        "title": "P0.8: Golden replay CI pipeline (GitHub Actions)",
        "body": """## Description

Set up CI pipeline that runs `alpha-quant replay --fixture` and asserts output hash matches committed golden file.

## Acceptance Criteria

- [ ] GitHub Actions runs on PR + push to main
- [ ] Runs: ruff check, mypy --strict, pytest
- [ ] Golden replay: `--output golden_run.json` produces canonical output
- [ ] CI compares SHA256 hash against `fixtures/golden/golden_run.json`
- [ ] `make bless-golden` updates golden file on intentional changes
- [ ] CI completes in <10 minutes

## Technical Details

- Golden output: `decision_log.json + equity_curve.json` — SHA256 of concatenated deterministic JSON
- CI matrix: Python 3.12, macOS + Ubuntu""",
        "labels": ["story", "priority/p0", "size/xs:1", "domain/backend", "P0"],
    },
    # ── Epic 1: Data Layer ──
    {
        "title": "P1.1: Shared connector machinery (base class, rate limiting, retry, vault-write)",
        "body": """## Description

Implement the base connector infrastructure: httpx client, tenacity retry, token-bucket rate limiter, automatic vault-write.

## Acceptance Criteria

- [ ] `BaseConnector` abstract class with httpx.Client, configurable timeouts, user-agent
- [ ] `fetch(url, params, source_name)` — rate-limited, retried, vault-written
- [ ] Token-bucket rate limiter: configurable tokens/second and max burst
- [ ] User-Agent from config (mandatory descriptive for SEC)
- [ ] Vault write synchronous and content-addressable
- [ ] structlog debug log per fetch: source, URL, status, latency, byte size

## Technical Details

- TokenBucket class (~30 lines): refill based on `time.monotonic()`, `consume(tokens=1)`
- tenacity: `stop_after_attempt(5)`, `wait_exponential(multiplier=1, min=2, max=30)`, `retry_on 429/5xx`
- 429 retry-after header respected""",
        "labels": ["story", "priority/p0", "size/m:3", "domain/backend", "P1"],
    },
    {
        "title": "P1.2: EODHD connector (bars, fundamentals, earnings calendar)",
        "body": """## Description

Implement the EODHD connector for daily bars, fundamentals snapshots, and earnings calendar. Primary market data source.

## Acceptance Criteria

- [ ] `daily_bars(symbol, start, end)` returns list of Bar models
- [ ] `fundamentals_snapshot(symbol)` returns FundamentalsSnapshot (OCF, D/E, Revenue, NetIncome, Accruals)
- [ ] `earnings_calendar(start, end)` returns list of EarningsDate
- [ ] Batch endpoint for daily Δ: `/eod-bulk-last-day/{exchange}`
- [ ] Rate limiting per EODHD plan
- [ ] All raw JSON goes to vault before parsing
- [ ] Fixture file parses correctly; invalid data raises DataNormalizationError

## Technical Details

- API base: `https://eodhd.com/api/`, auth: `?api_token={key}`
- Bar model: `symbol, date, open, high, low, close, adjusted_close, volume`
- Fundamentals: parse nested JSON for OCF, TotalDebt, TotalEquity, Revenue, NetIncome, Accruals""",
        "labels": ["story", "priority/p0", "size/m:3", "domain/backend", "P1"],
    },
    {
        "title": "P1.3: Alpaca data connector (informational only, no trading)",
        "body": """## Description

Implement Alpaca connector using `alpaca-py` data module only. Provides latest quotes (for spread estimation) and trading calendar. Trading module never imported.

## Acceptance Criteria

- [ ] `latest_quote(symbol)` returns Quote (bid, ask, bid_size, ask_size, timestamp)
- [ ] `trading_calendar(start, end)` returns list of market dates
- [ ] `latest_bar(symbol)` returns latest Bar for position marking
- [ ] Uses `StockHistoricalDataClient` only — no TradingClient
- [ ] Import lint rule: `alpaca.trading` in any file fails CI
- [ ] On unreachable: SOURCE_DEGRADED event, spread model falls back to 10 bps

## Technical Details

- Import: `from alpaca.data.historical import StockHistoricalDataClient`
- Spread estimate: `(ask - bid) / mid` or default 0.001
- Lint rule: CI grep `! grep -r "alpaca\\.trading" src/`""",
        "labels": ["story", "priority/p0", "size/s:2", "domain/backend", "P1"],
    },
    {
        "title": "P1.4: SEC ticker map connector",
        "body": """## Description

Implement the SEC connector for `company_tickers.json`. Authoritative ticker → CIK → exchange mapping.

## Acceptance Criteria

- [ ] `ticker_map()` returns `dict[str, TickerRecord]` with ticker, cik, name, exchange, sic_code
- [ ] Fetches from SEC with compliant User-Agent
- [ ] User-Agent configurable in config.toml
- [ ] Rate limit: 1 req/sec (SEC fair access)
- [ ] Caches to SQLite with timestamp; weekly refresh
- [ ] On failure: uses last-good cache, SOURCE_DEGRADED event

## Technical Details

- SEC format: `{"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}`
- CIK zero-padded to 10 digits
- UA format: `"CompanyName (contact@example.com)"` — mandatory""",
        "labels": ["story", "priority/p0", "size/xs:1", "domain/backend", "P1"],
    },
    {
        "title": "P1.5: OpenInsider connector (insider cluster data)",
        "body": """## Description

Implement OpenInsider connector for insider transaction cluster data. Backs M5 (insider cluster signal).

## Acceptance Criteria

- [ ] `recent_clusters(days=30)` returns list of InsiderCluster (symbol, avg_price, shares, value, type, officer_count, director_count)
- [ ] `cluster_for_symbol(symbol, days=30)` returns single InsiderCluster or None
- [ ] Parses HTML via selectolax from OpenInsider screener pages
- [ ] Rate limit: 1 req/3s, configurable burst
- [ ] Same-day responses served from vault cache
- [ ] On failure: SOURCE_DEGRADED → M5 neutral

## Technical Details

- Target: `http://openinsider.com/screener?...`
- Parse table rows, extract ticker, insider name, title, transaction type, price, qty, value, date
- Cluster: ≥2 officers/directors, ≥$200k net in 30 days""",
        "labels": ["story", "priority/p1", "size/m:3", "domain/backend", "P1"],
    },
    {
        "title": "P1.6: Reddit public sentiment connector",
        "body": """## Description

Implement Reddit connector using public JSON endpoints. Provides mention counts for M6 crowding veto. No API key needed.

## Acceptance Criteria

- [ ] `mention_counts(symbol, days=30, subreddits=["wallstreetbets","stocks"])` returns MentionCounts
- [ ] `baseline(symbol, window_days=30)` returns MentionBaseline (mean, std, z_score)
- [ ] Fetches from `https://www.reddit.com/r/{sub}/new.json`
- [ ] Rate limit: 10 req/min (unauthenticated)
- [ ] Case-insensitive ticker matching, common-word filter
- [ ] Count arithmetic only — no LLM sentiment
- [ ] On failure: SOURCE_DEGRADED → M6 fail-open with raised entry bar

## Technical Details

- Regex `\\b(AAPL|MSFT|...)\\b` from universe symbols
- Common-word filter: DD, RH, IT, GO, EV, AI, CEO, CFO, etc.
- Z-score: `(current - mean) / std` over 30 days; z>3 → 10-day block""",
        "labels": ["story", "priority/p1", "size/s:2", "domain/backend", "P1"],
    },
    {
        "title": "P1.7: Raw vault implementation (append-only, zstd, content-addressed)",
        "body": """## Description

Implement `vault.py`: append-only, content-addressed, zstd-compressed raw payload archive. Never delete or rewrite.

## Acceptance Criteria

- [ ] `store(source, endpoint, params, data_bytes, ingest_ts)` writes compressed blob to `vault/{source}/{yyyy}/{mm}/{dd}/{fetch_id}.zst`
- [ ] `read(fetch_id)` returns decompressed bytes
- [ ] `read_manifest(source, start, end)` returns manifest entries
- [ ] `dates_for_source(source)` returns set of dates with data
- [ ] Manifest is DuckDB database with: fetch_id, source, endpoint, params, ingest_ts, content_hash, byte_size
- [ ] Concurrent writes safe (DuckDB WAL mode)
- [ ] Duplicate content-addressable fetch_id skips gracefully

## Technical Details

- `fetch_id = sha256(f"{source}|{endpoint}|{json_params}|{ingest_ts}")[:16].hex()`
- zstd: `zstandard.ZstdCompressor(level=3).compress(data)`""",
        "labels": ["story", "priority/p0", "size/s:2", "domain/backend", "P1"],
    },
    {
        "title": "P1.8: Normalization — pydantic models + parsers for all sources",
        "body": """## Description

Implement `normalize.py` with pydantic models and parser functions for each source. Parse-don't-validate at zone boundaries.

## Acceptance Criteria

- [ ] `normalize_eodhd_bars(raw_json) -> list[Bar]`
- [ ] `normalize_eodhd_fundamentals(raw_json) -> FundamentalsSnapshot`
- [ ] `normalize_alpaca_quote(raw) -> Quote`
- [ ] `normalize_sec_tickers(raw_json) -> dict[str, TickerRecord]`
- [ ] `normalize_openinsider_html(raw_html) -> list[InsiderTransaction]`
- [ ] `normalize_reddit_mentions(raw_json) -> list[Mention]`
- [ ] All are pure functions: `raw_bytes -> Optional[CanonicalModel]`
- [ ] Invalid data returns None + log warning

## Technical Details

- All canonical models: frozen pydantic BaseModels
- OpenInsider HTML via selectolax CSS selectors
- InsiderTransaction: `symbol, filed_date, transaction_date, insider_name, title, transaction_type, shares, price, value, is_direct`""",
        "labels": ["story", "priority/p0", "size/m:3", "domain/backend", "P1"],
    },
    {
        "title": "P1.9: Canonical store — Parquet/DuckDB + SQLite StateStore",
        "body": """## Description

Implement canonical store: analytical data → date-partitioned Parquet via DuckDB; transactional state → SQLite WAL.

## Acceptance Criteria

- [ ] `write_bars()` appends to `canonical/bars/date=YYYY-MM-DD/part.parquet`
- [ ] `read_bars(symbol, start, end)` returns polars DataFrame
- [ ] `write_fundamentals()` / `write_insider_transactions()` / `write_mentions()` with date partitioning
- [ ] SQLite StateStore creates schema: decisions, orders, fills, positions, equity_curve, events, concept_log, indicator_state, catalog
- [ ] All writes transactional (WAL mode, batch commits)
- [ ] Double-ingest produces zero new rows (idempotency)
- [ ] 50-day tail prune by removing old date partitions

## Technical Details

- Parquet via pyarrow: `pq.write_table(table, path, compression="zstd")`
- DuckDB: `SELECT * FROM read_parquet('canonical/bars/**/*.parquet', hive_partitioning=true) WHERE symbol=?`
- SQLite schema uses SQLAlchemy Core (no ORM)""",
        "labels": ["story", "priority/p0", "size/l:5", "domain/backend", "P1"],
    },
    {
        "title": "P1.10: Incremental indicator engine (numpy, O(1) recurrence)",
        "body": """## Description

Implement `derive.py`: O(1) incremental calculation of EMA(20/50/200), RSI(14), ATR(14), MACD via numpy recurrence. No pandas-ta.

## Acceptance Criteria

- [ ] `update_indicator_state(state, new_bar) -> IndicatorState` — O(1) per symbol
- [ ] All indicators: EMA, RSI (Wilder), ATR, MACD line/signal/histogram
- [ ] `backfill_indicator_state(bars) -> IndicatorState` seeds from full history
- [ ] Integrity: recompute from 250-day brute-force → matches to 1e-6
- [ ] Performance: 10,000 symbols × 1 update < 10ms

## Technical Details

- EMA: `new_ema = price * alpha + prev_ema * (1 - alpha)`
- RSI Wilder: `avg_gain = prev * 13/14 + gain * 1/14`
- ATR: `atr = prev * 13/14 + tr * 1/14`
- All numpy, zero loops""",
        "labels": ["story", "priority/p0", "size/m:3", "domain/quant", "P1"],
    },
    {
        "title": "P1.11: Validation gates (quality checks between every zone)",
        "body": """## Description

Implement `validate.py` with declarative checks: price sanity, calendar gaps, staleness, schema drift. ~15 predicate functions.

## Acceptance Criteria

- [ ] `validate_bar(bars)` checks: no zero/negative prices, no |return|>40% without corp action, no date gaps, no NaN/Inf, volume>0
- [ ] `validate_fundamentals(snapshot)` — schema drift detection → quarantined
- [ ] `validate_staleness(last_update, threshold)` → StalenessHaltSet
- [ ] `validate_indicator_state(state)` — NaN detection → quarantined
- [ ] Quarantined symbols excluded from universe until manual clear
- [ ] All validators are pure functions: `(data) -> list[ValidationResult]`

## Technical Details

- ValidationResult: `is_valid, issues, severity (WARN/QUARANTINE/HALT)`
- Quarantine list in SQLite: `quarantine(symbol, reason, date, cleared)`
- Halt via lockfile `data/.HALT`""",
        "labels": ["story", "priority/p0", "size/s:2", "domain/backend", "P1"],
    },
    {
        "title": "P1.12: Catalog + dataset versioning",
        "body": """## Description

Implement `catalog.py` for dataset versioning, manifest tracking, fixture integrity verification.

## Acceptance Criteria

- [ ] `register_run(run_type, config_hash, fixture_version)` stores run metadata
- [ ] `verify_fixture_integrity(fixture_path, manifest)` checks content hashes
- [ ] `list_runs(since_date)` returns run history
- [ ] Golden replay uses catalog to verify hash match
- [ ] Fixture tampering causes integrity check failure

## Technical Details

- Catalog table: `run_id, run_type, config_hash, fixture_version, start_ts, end_ts, status`
- Manifest: sort files by path, concatenate, SHA256""",
        "labels": ["story", "priority/p1", "size/xs:1", "domain/backend", "P1"],
    },
    # ── Epic 2: Domain + Backtest + Paper ──
    {
        "title": "P2.1: Domain models (Candidates, Positions, Orders, Decisions)",
        "body": """## Description

Implement all frozen domain models in `domain/models.py`. Shared vocabulary across the entire system.

## Acceptance Criteria

- [ ] Candidate: symbol, date, scores, composite_score, regime, gate results, block_reason
- [ ] Position: symbol, entry/current price, shares, cost_basis, stop/trail prices, sector, decision_id
- [ ] Order: order_id, symbol, action, type, quantity, status, fill_date
- [ ] Decision: decision_id, run_id, date, symbol, action, candidate, position, order, risk/mechanism results
- [ ] All models: frozen pydantic BaseModel, cross-field validation
- [ ] All dates: `datetime.date`, monetary: `float`

## Technical Details

- `model_config = ConfigDict(frozen=True)`
- Sector lookup from static CSV map""",
        "labels": ["story", "priority/p0", "size/s:2", "domain/quant", "P2"],
    },
    {
        "title": "P2.2: Universe selection (M1)",
        "body": """## Description

Implement M1 universe selection: filter by liquidity, price, SEC-map validity. Produces tradeable candidates.

## Acceptance Criteria

- [ ] `select(date, all_symbols, market_data, fundamentals) -> list[UniverseMember]`
- [ ] Filters: price ≥ $5, ADV ≥ $5M, valid SEC CIK, not quarantined, recent price data
- [ ] Returns: `UniverseMember(symbol, price, volume_adv, market_cap, sector, passes_m1, fail_reason)`
- [ ] 5000 symbols in < 50ms

## Technical Details

- ADV: median daily dollar volume over 20 trading days
- SEC map cache loaded at pipeline start""",
        "labels": ["story", "priority/p0", "size/s:2", "domain/quant", "P2"],
    },
    {
        "title": "P2.3: Regime detection (M2) — RISK_ON / CAUTION / RISK_OFF",
        "body": """## Description

Implement M2 regime gate: classify market as RISK_ON, CAUTION, or RISK_OFF based on SPY trend, breadth, VIX.

## Acceptance Criteria

- [ ] `detect(spy_bars, spy_indicator, vix_level, breadth_data) -> Regime`
- [ ] RISK_ON: SPY > EMA50 > EMA200 AND VIX < 20 AND breadth > 0.4
- [ ] RISK_OFF: SPY < EMA200 OR VIX > 30
- [ ] CAUTION: everything else
- [ ] Position size multipliers: RISK_ON=1.0, CAUTION=0.5, RISK_OFF=0.0
- [ ] RegimeChanged event on switch

## Technical Details

- Breadth: percentage of SP500 > 50-day SMA (approx from universe)
- VIX via configured symbol""",
        "labels": ["story", "priority/p0", "size/m:3", "domain/quant", "P2"],
    },
    {
        "title": "P2.4: Technical score (M3) — trend, RSI, MACD, volume, ATR sanity",
        "body": """## Description

Implement M3 technical scoring: composite from trend, momentum, RSI zone, MACD histogram, volume, ATR sanity.

## Acceptance Criteria

- [ ] `score(symbol, bars, indicator) -> TechnicalScore (0.0–1.0)`
- [ ] Sub-scores: trend (price/EMA50), momentum (12-1 return), RSI zone (45–70), MACD, volume confirmation, ATR sanity
- [ ] Composite via weighted average
- [ ] Bull flag → high score; declining stock → low score

## Technical Details

- All inputs from IndicatorState + raw bars
- Momentum: `(close_12mo - close_1mo) / close_1mo` from month-end closes""",
        "labels": ["story", "priority/p0", "size/m:3", "domain/quant", "P2"],
    },
    {
        "title": "P2.5: Fundamental quality gate (M4) — binary pass/fail",
        "body": """## Description

Implement M4 fundamental quality gate: pass/fail on OCF, D/E, accruals, earnings surprise.

## Acceptance Criteria

- [ ] `evaluate(symbol, fundamentals) -> QualityVerdict`
- [ ] Checks: OCF > 0, D/E < sector median × 2, accruals ratio in [-0.05, 0.05], no recent negative surprise
- [ ] Missing fundamentals → pass with SOURCE_DEGRADED event

## Technical Details

- Accruals: `(Net Income - OCF) / Average Total Assets`
- Sector median D/E computed per sector from universe""",
        "labels": ["story", "priority/p0", "size/s:2", "domain/quant", "P2"],
    },
    {
        "title": "P2.6: Earnings blackout (M7)",
        "body": """## Description

Implement M7: block new entries within 3 trading days before earnings.

## Acceptance Criteria

- [ ] `check(symbol, date, earnings_calendar) -> BlackoutVerdict`
- [ ] Blackout window: 3 trading days before report
- [ ] Unknown earnings date → pass

## Technical Details

- Calendar from EODHD, stored in SQLite
- Trading days via Clock port""",
        "labels": ["story", "priority/p0", "size/xs:1", "domain/quant", "P2"],
    },
    {
        "title": "P2.7: Composite ranking (M8) — weighted + gated",
        "body": """## Description

Implement M8: combine M3/M5 scores with weights, apply gates (M1,M4,M6,M7), rank, produce entry list.

## Acceptance Criteria

- [ ] `rank(candidates, regime, current_positions) -> list[RankedCandidate]`
- [ ] Formula: `0.6 * technical + 0.25 * momentum + 0.15 * insider`
- [ ] Gates applied first (hard filter), ties broken by ADV
- [ ] Only >0.5 considered; top N = max_positions - current

## Technical Details

- No insider data → 0.70 technical + 0.30 momentum
- Degradation per §3.2""",
        "labels": ["story", "priority/p0", "size/xs:1", "domain/quant", "P2"],
    },
    {
        "title": "P2.8: Position sizing (Kelly-lite + risk parity)",
        "body": """## Description

Implement position sizing: `shares = (equity × 1%) / (2 × ATR)`, with caps + regime/DD multipliers.

## Acceptance Criteria

- [ ] `size_position(equity, price, atr, regime_mult, dd_mult, config) -> PositionSize`
- [ ] Base: risk-normalized notional
- [ ] Caps: max 15%/pos, gross 80%, max 2/sector
- [ ] Regime: ×1/0.5/0, DD: ×1/0.5/0
- [ ] Returns: shares, notional, risk_at_stop, capped_by list

## Technical Details

- `shares = int(notional / price)` — round down
- `risk_at_stop <= 2% equity` (I5)""",
        "labels": ["story", "priority/p0", "size/s:2", "domain/quant", "P2"],
    },
    {
        "title": "P2.9: Risk management — stops, trails, takes, drawdown, halts",
        "body": """## Description

Implement risk.py: stops (2×ATR), trailing, partial takes (+2R), time stops (30d), drawdown ladder, daily loss halt. Exit-only.

## Acceptance Criteria

- [ ] `evaluate_stops(position, bar, config)` — initial stop, trail after +1R, partial at +2R
- [ ] `evaluate_time_stop(position, date, config)` — close if > 30 days
- [ ] `evaluate_drawdown(equity_curve, config)` — 10%→×0.5, 15%→flat
- [ ] `evaluate_daily_loss(pnl, equity, config)` — -3% halt
- [ ] All return list[RiskAction] with type, position_id, shares, reason

## Technical Details

- Stop touch vs daily bar: `if bar.low <= stop_price -> exit`
- `highest_since_entry` tracked in Position
- Drawdown from equity curve peak""",
        "labels": ["story", "priority/p0", "size/m:3", "domain/quant", "P2"],
    },
    {
        "title": "P2.10: Fill model — THE fill model (backtest, replay, paper, shadows)",
        "body": """## Description

Implement `domain/fills.py`: THE fill model. One function, five consumers. Conservative semantics — gap-through-stop fills at open.

## Acceptance Criteria

- [ ] `fill_entry_order(order, bar, quote, config)` — fill at open + slippage, cancel on gap > 0.2%
- [ ] `fill_stop_order(position, stop, bar, config)` — stop touched → fill at min(open, stop) - slippage
- [ ] `fill_partial_take(position, take, bar, config)` — sell 50%
- [ ] `apply_corporate_action(position, ca)` — dividends/splits
- [ ] Idempotent: `fill_id = sha256(decision_id | fill_date)`
- [ ] Gap-through-stop fills at open, not stop

## Technical Details

- Slippage: 5 bps + half-spread from Alpaca quote
- Half-spread: `(ask - bid) / (2 * mid)` or 0.001
- Deterministic: re-running same day produces same fills""",
        "labels": ["story", "priority/p0", "size/l:5", "domain/quant", "P2"],
    },
    {
        "title": "P2.11: Paper portfolio engine",
        "body": """## Description

Implement `app/paper.py`: authoritative paper portfolio in SQLite. Cash, positions, orders, fills, equity curve.

## Acceptance Criteria

- [ ] `init(equity, date)` — sets cash, first equity curve point
- [ ] `process_risk_actions(actions, bar, quote)` — executes exits via fill model
- [ ] `process_entry_orders(candidates, bar, quote)` — creates/fills entry orders
- [ ] `mark_to_market(date, data)` — updates marks, records equity
- [ ] `self_consistency_check()` — cash + mark == equity, traceable lineage
- [ ] All writes in single SQLite transaction
- [ ] Positions trace to fills → orders → decisions (I1)

## Technical Details

- Daily cycle: T close → decide → T+1 open → fill → mark
- Transactional: rollback on any error
- Self-consistency: tolerance 1 cent""",
        "labels": ["story", "priority/p0", "size/l:5", "domain/backend", "P2"],
    },
    {
        "title": "P2.12: Shadow ablation books (RULES_ONLY, NO_INSIDER, NO_CROWDING_VETO)",
        "body": """## Description

Implement shadow books with mechanism toggles that run alongside PAPER. Live ablation, walk-forward by construction.

## Acceptance Criteria

- [ ] ShadowBook with mechanism_toggles dict
- [ ] RULES_ONLY: M5=0, M6 disabled
- [ ] NO_INSIDER: M5 disabled
- [ ] NO_CROWDING_VETO: M6 disabled
- [ ] SPY buy-and-hold curve
- [ ] Same fill model as PAPER (I8)
- [ ] All books update on every run (I11)
- [ ] Comparison: Sharpe difference, flag after 2 quarters underperforming

## Technical Details

- Shadow books share Store under different table namespaces
- Toggles dict: `{"insider_boost": False, "crowding_veto": False}`""",
        "labels": ["story", "priority/p1", "size/m:3", "domain/quant", "P2"],
    },
    {
        "title": "P2.13: Backtester (event-driven, no vectorbt)",
        "body": """## Description

Implement event-driven backtester: daily loop over same fill model. Path-dependent decisions require step-by-step simulation.

## Acceptance Criteria

- [ ] `run(start, end, symbols, config) -> BacktestResult`
- [ ] Daily loop: ingest → derive → risk → decide → order → fill → mark
- [ ] Same fill model as paper (I8)
- [ ] Output: equity_curve, decisions, fills, events, metrics (CAGR, DD, Sharpe, Sortino, etc.)
- [ ] 10 years × 50 symbols < 60 seconds
- [ ] Hand-computed 5-trade scenario matches exactly

## Technical Details

- One fill model across all execution realities (I8)
- Metrics: numpy-based""",
        "labels": ["story", "priority/p0", "size/m:3", "domain/quant", "P2"],
    },
    {
        "title": "P2.14: Daily pipeline orchestrator",
        "body": """## Description

Implement `app/pipeline.py`: sequences ingest → validate → derive → regime → risk → decide → order → persist.

## Acceptance Criteria

- [ ] `run(date, ...) -> RunResult` — full sequence per DESIGN §13
- [ ] Degradation: connector failure → SOURCE_DEGRADED, pipeline continues
- [ ] DATA_HALT: stops at staleness
- [ ] Shadow books run after paper
- [ ] Dependency-injected adapters

## Technical Details

- All errors caught at pipeline level, emitted as events
- Weekly rebalance: fill all vacancies on designated day""",
        "labels": ["story", "priority/p0", "size/l:5", "domain/backend", "P2"],
    },
    {
        "title": "P2.15: Self-consistency & invariants enforcement",
        "body": """## Description

Implement self-consistency checks after every fill batch. Violation = software bug = full halt.

## Acceptance Criteria

- [ ] `check(portfolio, store)` — cash+mark == equity, traceable lineage, no orphans
- [ ] Risk-at-stop ≤ 2% equity (I5), gross ≤ cap (I6)
- [ ] Violation → ConsistencyViolation event + halt lockfile
- [ ] `status` shows HALTED with violation details

## Technical Details

- Tolerance: `abs(cash+mark - equity) < 0.01`
- Halt file: `data/.HALT` with reason, run_id, date""",
        "labels": ["story", "priority/p0", "size/xs:1", "domain/backend", "P2"],
    },
    # ── Epic 3: Alt-Data Signals ──
    {
        "title": "P3.1: Insider cluster signal (M5)",
        "body": """## Description

Implement M5: detect insider buying clusters (≥2 officers, ≥$200k, 30d) → score boost for M8.

## Acceptance Criteria

- [ ] `evaluate(symbol, transactions, lookback=30) -> InsiderVerdict`
- [ ] Cluster: ≥2 officers/directors, ≥$200k net in 30 days
- [ ] Score boost: 0.15 if detected, 0.0 otherwise
- [ ] Degraded source → boost = 0

## Technical Details

- Cohen/Malloy/Pomorski (2012) methodology
- Only open-market purchases, exclude option exercises""",
        "labels": ["story", "priority/p1", "size/m:3", "domain/quant", "P3"],
    },
    {
        "title": "P3.2: Crowding veto (M6) — Reddit z-score > 3",
        "body": """## Description

Implement M6: Reddit mention z-score > 3 → 10-day entry block. Count arithmetic only.

## Acceptance Criteria

- [ ] `evaluate(symbol, mention_data) -> CrowdingVerdict`
- [ ] Block if z > 3 for 10 trading days
- [ ] Degraded source → block lifted, M3 threshold +20%

## Technical Details

- Z-score: `(daily - mean_30d) / std_30d`
- Block state in SQLite: `crowding_block(symbol, blocked_until, reason)`""",
        "labels": ["story", "priority/p1", "size/s:2", "domain/quant", "P3"],
    },
    {
        "title": "P3.3: Shadow ablation books activation (NO_INSIDER + NO_CROWDING_VETO)",
        "body": """## Description

Activate NO_INSIDER and NO_CROWDING_VETO shadow books. Implement ablation comparison and auto-flagging.

## Acceptance Criteria

- [ ] Both books run every pipeline execution
- [ ] Correct mechanism toggles applied
- [ ] Ablation comparator computes rolling Sharpe diff per mechanism
- [ ] Flag if ablation beats PAPER for 2 consecutive quarters

## Technical Details

- Comparison stored in SQLite
- Flagged mechanisms disabled until manual review""",
        "labels": ["story", "priority/p1", "size/m:3", "domain/quant", "P3"],
    },
    {
        "title": "P3.4: Source degradation fallback integration",
        "body": """## Description

Implement degrade-don't-block: each source failure has defined fallback per DESIGN §3.2.

## Acceptance Criteria

- [ ] OpenInsider down → M5 boost=0
- [ ] Reddit down → M6 disabled, M3 threshold +20%
- [ ] EODHD fundamentals down → M4 pass with degraded event
- [ ] Earnings calendar stale → blackout window +1 day
- [ ] SEC down → last-good cache

## Technical Details

- Degradation state in SQLite: `source_degradation(source, since, last_ok, payload)`
- Fallbacks in mechanism functions, not connectors""",
        "labels": ["story", "priority/p1", "size/s:2", "domain/backend", "P3"],
    },
    # ── Epic 4: Narration & Education ──
    {
        "title": "P4.1: LLM adapter (OpenAI + OpenRouter)",
        "body": """## Description

Implement LLM port adapter for OpenAI-compatible APIs. One code path for both providers via configurable base_url.

## Acceptance Criteria

- [ ] Configurable provider, model, api_key, base_url, timeout
- [ ] `explain(context) -> str` — sends rendered facts, returns prose
- [ ] `generate_card(concept) -> str` — generates concept explanation
- [ ] httpx directly (no OpenAI SDK), timeout 30s, tenacity retry 3×
- [ ] API key from config (SecretStr), masked in logs
- [ ] Outage → template fallback

## Technical Details

- POST `{base_url}/chat/completions` with system + user message
- Temperature 0.3 for deterministic output""",
        "labels": ["story", "priority/p1", "size/s:2", "domain/backend", "P4"],
    },
    {
        "title": "P4.2: Narration context builder",
        "body": """## Description

Build NarrationContext from events/lineage: all numbers the LLM is allowed to mention. Never raw data.

## Acceptance Criteria

- [ ] `build(date, events, decisions, positions, regime, metrics) -> NarrationContext`
- [ ] Contains: regime, data health, candidate funnel, positions, risk map, equity, concept of day
- [ ] All numbers from events, never LLM or raw data
- [ ] Frozen pydantic model, serializable

## Technical Details

- Risk map: `(current_price - stop_price) / equity * 100`
- Concept rotation from concept_log in SQLite""",
        "labels": ["story", "priority/p1", "size/m:3", "domain/backend", "P4"],
    },
    {
        "title": "P4.3: Fact-checker — post-LLM verification",
        "body": """## Description

Verify every number in LLM output exists in source NarrationContext. On mismatch → fall back to plain template.

## Acceptance Criteria

- [ ] `verify(llm_output, context) -> VerificationResult`
- [ ] Extract numbers via regex, check against context allowlist
- [ ] Hallucinated number → fail → template fallback

## Technical Details

- Number regex: `\\b\\d+(?:\\.\\d+)?(?:%|bps|USD)?\\b`
- Template: simple string formatting from context""",
        "labels": ["story", "priority/p1", "size/s:2", "domain/backend", "P4"],
    },
    {
        "title": "P4.4: Concept card registry (~20 cards)",
        "body": """## Description

Write 20 hand-crafted concept cards (Markdown): ATR, stop-loss, regime, RSI, MACD, drawdown, etc.

## Acceptance Criteria

- [ ] 20 concept cards in `concepts/` as `.md` files
- [ ] Each: title, difficulty, 2-3 paragraph explanation, key takeaway
- [ ] Registry manifest: `concepts.json` with metadata

## Technical Details

- Frontmatter: `--- id: atr title: \"What is ATR?\" difficulty: beginner ---`""",
        "labels": ["story", "priority/p1", "size/m:3", "domain/frontend", "P4"],
    },
    {
        "title": "P4.5: Daily journal generator",
        "body": """## Description

Generate daily journal Markdown: regime, actions, risk map, concept card. Output to SQLite.

## Acceptance Criteria

- [ ] Sections: Market Overview, Data Health, Today's Actions, Risk Map, Non-Actions, Concept of Day, Key Numbers
- [ ] Negative-space narration: "no trades today because..."
- [ ] Stored in SQLite `journal_entries`

## Technical Details

- Markdown, not HTML
- Concept of day: rotate through 20 cards""",
        "labels": ["story", "priority/p1", "size/s:2", "domain/frontend", "P4"],
    },
    {
        "title": "P4.6: Weekly & monthly reports",
        "body": """## Description

Generate weekly review and monthly performance reports with ablation scoreboard.

## Acceptance Criteria

- [ ] Weekly: rebalance rationale, candidate funnel, book deltas, blackouts
- [ ] Monthly: PAPER vs SPY vs shadows, attribution, turnover, cost drag, caveat
- [ ] Markdown, stored in SQLite

## Technical Details

- Monthly runs last trading day of month
- Attribution: paper vs ablation equity difference""",
        "labels": ["story", "priority/p1", "size/s:2", "domain/frontend", "P4"],
    },
    {
        "title": "P4.7: Streamlit dashboard",
        "body": """## Description

Build read-only Streamlit dashboard: equity curve, positions, risk map, reports, concept cards.

## Acceptance Criteria

- [ ] Tabs: Overview, Portfolio, Risk, Reports, Concepts
- [ ] Reads from SQLite only — no pipeline coupling
- [ ] All charts render without errors on fixture data

## Technical Details

- Stack: Streamlit + altair/plotly
- Auto-refresh every 60s live""",
        "labels": ["story", "priority/p1", "size/m:3", "domain/frontend", "P4"],
    },
    {
        "title": "P4.8: `ask` command — query recorded decisions",
        "body": """## Description

Implement `alpha-quant ask "why not TSLA?"` — answers from recorded CandidateBlocked events. LLM polishes, never generates reasoning.

## Acceptance Criteria

- [ ] Queries last N days of CandidateBlocked events for the symbol
- [ ] Never generated in LLM — always from recorded events
- [ ] Unknown symbol → "no record of evaluating"
- [ ] Concept query → returns concept card

## Technical Details

- Query path: events → CandidateBlocked → format → LLM polish → fact-check""",
        "labels": ["story", "priority/p1", "size/s:2", "domain/frontend", "P4"],
    },
    # ── Epic 5: Live Data Operations ──
    {
        "title": "P5.1: Real connector configuration & activation",
        "body": """## Description

Wire up all 5 real connectors for live operation. API keys from config, rate-limiting, vault-writing.

## Acceptance Criteria

- [ ] All connectors load with real API keys (SecretStr)
- [ ] `run --live` runs full pipeline with real connectors
- [ ] Rate limiters active
- [ ] Vault stores raw responses (I4)
- [ ] `status --check-connections` pings each source

## Technical Details

- Factory: `create_market_data(config)` returns real vs fixture based on `config.mode`
- Connection check: lightweight health endpoint""",
        "labels": ["story", "priority/p1", "size/m:3", "domain/ops", "P5"],
    },
    {
        "title": "P5.2: Scheduling (APScheduler + cron fallback)",
        "body": """## Description

Set up APScheduler at 17:30 ET daily. Cron fallback documented.

## Acceptance Criteria

- [ ] Fires daily at 17:30 ET on trading days
- [ ] Idempotent: duplicate trigger = no-op (check run_id)
- [ ] Logs to file with rotation
- [ ] Cron fallback entry in docs

## Technical Details

- `CronTrigger` with timezone=America/New_York, hour=17, minute=30
- Idempotency: check runs table for today""",
        "labels": ["story", "priority/p1", "size/s:2", "domain/ops", "P5"],
    },
    {
        "title": "P5.3: Alerting & notifications",
        "body": """## Description

Alert on critical events: DATA_HALT, drawdown, consistency violation, pipeline failure.

## Acceptance Criteria

- [ ] Immediate alerts: HALT, consistency violation, drawdown, pipeline failure
- [ ] Daily digest: source degradation, run completion
- [ ] Channels: console log, optional email (config)
- [ ] macOS desktop notification
- [ ] `status --alerts` shows recent alerts

## Technical Details

- Alert levels: CRITICAL, WARNING, INFO
- Email via smtplib if configured""",
        "labels": ["story", "priority/p1", "size/s:2", "domain/ops", "P5"],
    },
    {
        "title": "P5.4: Ops commands — status, halt, resume",
        "body": """## Description

Implement `status` (full system state), `halt` (kill switch), `resume` (clear halt).

## Acceptance Criteria

- [ ] `status`: system state, last run, data health, portfolio, regime, alerts, uptime
- [ ] `halt "reason"`: creates halt lockfile
- [ ] `resume`: clears halt (requires confirmation)
- [ ] `status --json`: machine-readable

## Technical Details

- Halt file: `data/.HALT` with reason, timestamp, run_id
- Pipeline checks .HALT at startup""",
        "labels": ["story", "priority/p1", "size/s:2", "domain/ops", "P5"],
    },
    {
        "title": "P5.5: Backup & recovery",
        "body": """## Description

Implement backup routine: SQLite + vault manifest. Document recovery.

## Acceptance Criteria

- [ ] `backup`: compressed archive of SQLite + vault manifest + config (redacted)
- [ ] Automatic daily backup after pipeline run
- [ ] Retention: 30 daily, 12 monthly
- [ ] Recovery doc: `docs/ops/RECOVERY.md`

## Technical Details

- SQLite: `.backup` command (hot backup)
- Backup path: `backups/alpha-quant-{date}-{sha}.tar.zst`""",
        "labels": ["story", "priority/p1", "size/s:2", "domain/ops", "P5"],
    },
    {
        "title": "P5.6: Unattended operation validation (chaos tests)",
        "body": """## Description

Validate 2-week unattended run. Chaos tests: kill mid-run, network loss, SQLite corruption, disk full.

## Acceptance Criteria

- [ ] Kill -9 mid-ingest → restart → idempotent
- [ ] Network disabled → SOURCE_DEGRADED → DATA_HALT on staleness → recover
- [ ] SQLite corruption → consistency check catches → halt
- [ ] Disk full → graceful error + halt
- [ ] 2-week log shows no crashes, clean daily runs

## Technical Details

- Chaos test scripts in `tests/chaos/`
- SQLite WAL + vault append-only guarantee atomicity per operation""",
        "labels": ["story", "priority/p1", "size/m:3", "domain/ops", "P5"],
    },
    # ── Epic 6: Evaluation ──
    {
        "title": "P6.1: Mechanism ablation analysis (3-month)",
        "body": """## Description

After ≥3 months paper trading, produce definitive mechanism ablation analysis. Every mechanism vs its ablation.

## Acceptance Criteria

- [ ] Per-mechanism: Sharpe, CAGR, DD, win rate PAPER vs ablation
- [ ] Bootstrap test (1000× resample) on Sharpe difference
- [ ] p > 0.10 → flagged for removal
- [ ] Cost analysis: turnover, slippage by mechanism
- [ ] Documented in `docs/evaluation/MECHANISM_ANALYSIS.md`

## Technical Details

- Bootstrap: sample daily returns 1000×, compare Sharpe distributions with scipy or custom numpy""",
        "labels": ["story", "priority/p2", "size/xl:8", "domain/quant", "P6"],
    },
    {
        "title": "P6.2: Parameter sensitivity analysis (walk-forward)",
        "body": """## Description

Test ≤3 tunable parameters across walk-forward windows.

## Acceptance Criteria

- [ ] Parameters: stop_atr_mult, risk_per_trade_pct, max_positions
- [ ] Walk-forward: 3y train, 1y test, roll by 6 months
- [ ] Grid: 3 values each → 27 combos
- [ ] Surface plots, optimal region, stability measure
- [ ] Documentation in `docs/evaluation/PARAMETER_ANALYSIS.md`

## Technical Details

- Walk-forward CV: simple nested loops
- Stability: CV of Sharpe across windows""",
        "labels": ["story", "priority/p2", "size/l:5", "domain/quant", "P6"],
    },
    {
        "title": "P6.3: Broker decision & live-gate criteria",
        "body": """## Description

Evaluate broker go/no-go: 3 months paper, Sharpe>0.5, DD<20%, mechanisms non-negative, zero violations, 2wk unattended.

## Acceptance Criteria

- [ ] All gates evaluated and documented
- [ ] Pass → recommendation: implement broker adapter (Alpaca trading module)
- [ ] Fail → address-specific, extend evaluation
- [ ] Documented in `docs/evaluation/BROKER_DECISION.md`

## Technical Details

- Broker adapter scope: Alpaca Broker API (trading module)
- Start with $10K, 50% of paper sizing""",
        "labels": ["story", "priority/p2", "size/l:5", "domain/ops", "P6"],
    },
]


def create_issue(issue_data):
    """Create a GitHub issue with labels."""
    labels = [l.split(":")[0] for l in issue_data["labels"]]
    label_args = []
    for label in labels:
        label_args.extend(["--label", label])

    cmd = [
        "gh",
        "issue",
        "create",
        "--repo",
        REPO,
        "--title",
        issue_data["title"],
        "--body",
        issue_data["body"],
    ] + label_args

    result = subprocess.run(cmd, capture_output=True, text=True)
    url = result.stdout.strip()
    if result.returncode != 0:
        print(f"FAILED: {issue_data['title']}")
        print(f"  {result.stderr.strip()}")
        return None
    else:
        print(f"CREATED: {issue_data['title']}")
        print(f"  {url}")
        return url


def main():
    print(f"Creating {len(ISSUES)} issues for {REPO}...\n")
    for i, issue in enumerate(ISSUES, 1):
        create_issue(issue)
        print()
    print(f"Done. Created {len(ISSUES)} issues.")


if __name__ == "__main__":
    main()

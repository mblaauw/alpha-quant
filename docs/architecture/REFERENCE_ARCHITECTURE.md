# Alpha-Quant — Reference Architecture

## 1. System Context

Alpha-Quant is a **deterministic strategy-policy and paper-trading engine**. It consumes point-in-time market facts exclusively from **Alpha-Lake** through a versioned authenticated REST API. Alpha-Quant owns decisions, portfolio controls, paper execution, journals, and replay — not market data.

### External Dependencies

| Dependency | Purpose | Protocol |
|------------|---------|----------|
| Alpha-Lake | All market facts (bars, indicators, fundamentals, insider, earnings, attention) | HTTPS REST (PIT `as_of` + optional `snapshot_id`) |
| OpenRouter/OpenAI (optional) | LLM narration and decision explanations | HTTPS REST |

### Non-Goals

- Market data ingestion, normalization, or storage
- Technical indicator calculation
- Fundamental ratio computation
- Sentiment/mention aggregation
- Source-provider management (EODHD, SEC, OpenInsider, Reddit)
- Live brokerage execution

## 2. Architecture Style

**Ports-and-Adapters (Hexagonal).** The domain boundary is `ports/alpha_lake.py:AlphaLakeReadPort` — all market facts flow through a single authenticated REST interface. No direct Python imports, DuckDB connections, or Parquet file access for market data.

## 3. Module Layout

```
src/alpha_quant/
├── ports/
│   └── alpha_lake.py          # AlphaLakeReadPort (Protocol)
├── contracts/
│   └── alpha_lake.py          # Data contracts (dataclasses)
├── domain/
│   ├── decision_context.py    # Fact context for policy modules
│   └── policy/                # Strategy policy modules
│       ├── regime_policy.py
│       ├── technical_policy.py
│       ├── fundamental_policy.py
│       ├── insider_policy.py
│       ├── attention_policy.py
│       ├── earnings_blackout_policy.py
│       ├── ranking_policy.py
│       └── composite_policy.py
├── adapters/
│   ├── real/
│   │   ├── alpha_lake_rest.py       # HTTP client
│   │   └── decision_store_duckdb.py # Local state store
│   └── fake/
│       ├── alpha_lake_http_fixture.py  # Offline replay
│       └── virtual_clock.py
└── app/
    ├── cli.py, config.py, factory.py
    ├── pipeline.py, replay.py, backtest.py
    └── store/                 # Local decision/paper state (DuckDB)
```

## 4. Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Runtime | Python 3.14 | Type hints, pattern matching, free-threaded |
| HTTP Client | httpx | Async-capable, connection pooling, timeout support |
| State Store | DuckDB | Embedded OLAP for local decision/paper state |
| CLI | Typer + Rich | Type-hint-driven commands, formatted tables |
| Type Checker | ty (Astral) | Fast, Python 3.14 compatible |
| Linter/Formatter | ruff (Astral) | Unified lint + format, 10-100x faster |
| Config | pydantic-settings + TOML | Type-safe environment overrides |

## 5. Architecture Decision Records

36 ADRs document every technology and architectural decision.

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
| 0014 | Streamlit Dashboard | Accepted |
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
| 0031 | File-Based Halt Mechanism | Accepted |
| 0033 | Clock-Driven PIT Reads | Accepted |
| 0035 | Alpha-Lake REST Is the Sole Facts Plane | **Accepted** |
| 0036 | Neutral Facts in Alpha-Lake, Strategy Policy in Alpha-Quant | **Accepted** |
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

### 6.1 Single REST Facts Port

All market facts enter through `AlphaLakeReadPort` — one protocol, one implementation per environment:

- **Production:** `AlphaLakeRestClient` (httpx → Alpha-Lake REST API)
- **Test/Replay:** `AlphaLakeHttpFixtureClient` (pre-recorded HTTP responses)

No other runtime data-access mechanism exists.

### 6.2 Point-in-Time (PIT) Determinism

Every decision, backtest, and replay run uses:
- `as_of` (mandatory): the knowledge-time boundary for all facts
- `snapshot_id` (mandatory for replay, recommended for backtests): pins to a specific Alpha-Lake catalog snapshot

This ensures byte-stable reproducibility: same config + same snapshot = same decisions.

### 6.3 Pessimistic Fill Model (ADR-0009)

The fill model remains the most distinctive architectural decision. It is shared across backtest, replay, paper, and shadow books:
- **Gap-through-stops**: if `bar.low <= stop_price`, fills at `min(open, stop_price) - slippage`
- **Gap-up entries**: cancels if the open gaps >2% above the decision quote
- **Partial fills**: scaled by `max_fill_pct` with a deterministic volume-based fill price

### 6.4 Policy over Facts

Strategy modules in `domain/policy/` apply thresholds and rules to Alpha-Lake observations. No policy recalculates a neutral metric. For example:

```python
# Correct: policy applies threshold to Alpha-Lake metric
rsi = context.indicator("momentum.rsi_14")
if rsi is not None and rsi > 70:
    return 0.0

# Wrong: never calculate RSI locally
# rsi = calc_rsi(bars, 14)  # forbidden
```

### 6.5 Ablation Framework (ADR-0030)

Shadow books run in parallel during every pipeline execution. Each book disables one mechanism (e.g., `NO_INSIDER`, `NO_CROWDING_VETO`) to measure its marginal contribution. Books share the same Alpha-Lake decision panel — the `as_of` and `snapshot_id` are identical across all books.

### 6.6 Halt Mechanism (ADR-0031)

A `.HALT` sentinel file prevents pipeline execution. Alpha-Lake unavailability, incompatible API contract, and stale facts are all halt reasons. The system fails closed — no silent fallback.

## 7. Runtime Flow

```
1. CLI: alpha-quant run --as-of T --snapshot-id S
2. Factory: instantiate AlphaLakeRestClient(base_url, api_key)
3. Client: GET /v1/contract → verify version + capabilities
4. Client: GET /v1/health → verify server readiness
5. Client: GET /v1/decision-panel?symbols=...&as_of=T&snapshot_id=S
6. Assembly: build DecisionContext for each symbol
7. Policy: apply regime → technical → fundamental → insider → crowding → blackout → ranking → composite
8. Portfolio: apply risk controls, position sizing
9. Execution: simulate paper orders and fills
10. Persist: store decisions, orders, fills, portfolio snapshot, evidence trail
```

## 8. Configuration

```toml
[alpha_lake]
base_url = "http://alpha-lake:8000"
api_key_env = "ALPHA_LAKE_API_KEY"

[strategy]
decision_mode = "paper"

[portfolio]
max_positions = 8
max_position_pct = 0.15

[risk]
max_drawdown_pct = 0.20
daily_loss_halt_pct = 0.03
```

## 9. Related Documents

- [ADR Index](../adr/README.md)
- [C4 Architecture Diagrams](./README.md)
- [DESIGN.md](../DESIGN.md)
- [Alpha-Lake API Documentation](https://github.com/mblaauw/alpha-lake)

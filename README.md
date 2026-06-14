<div align="center">

<div align="center">
  <img src="docs/assets/logo.png" alt="Alpha-Quant Logo" width="200">
</div>
# Alpha-Quant

Deterministic, daily-cadence, long-only equity paper-trading engine

[![CI](https://github.com/mblaauw/alpha-quant/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/mblaauw/alpha-quant/actions)
[![Beta Release](https://img.shields.io/badge/status-beta-yellow)](https://github.com/mblaauw/alpha-quant/milestone/8)
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://python.org)
[![ty checked](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

</div>

---

## Overview

Alpha-Quant is a deterministic, daily-cadence, long-only equity paper-trading system built on a ports-and-adapters (hexagonal) architecture. It evaluates US equities through a multi-mechanism decision engine (M1–M8), runs a conservative fill model shared across backtest and paper modes, and generates structured trading decisions with LLM-narrated daily journals.

**Who is this for?** Quantitative researchers and algorithmic traders who want to prototype, backtest, and paper-trade systematic equity strategies without a broker dependency. The system is designed for research transparency — every mechanism has an ablation counterpart for walk-forward validation, and the core domain logic is pure Python with zero I/O.

**What problem does it solve?** Bridging the gap between strategy research and paper execution with:
- A single fill model across backtest, paper, replay, and shadow books (no simulated/real divergence)
- Mechanism-level attribution (which factors drove each decision)
- Walk-forward validation infrastructure (shadow books that isolate each mechanism's contribution)
- Deterministic replay for auditability

> **⚠️ Beta status:** This is a research/paper-trading system. It is **not financial advice**. The decision engine is under active development — several mechanisms are implemented as domain logic but not yet wired into the runtime path (see [Beta Release milestone](https://github.com/mblaauw/alpha-quant/milestone/8) for open items).

### Key Principles

- **Deterministic** — same config + same data = same decisions, every run (I7)
- **Degrade, never block** — source failures degrade gracefully; only price staleness halts
- **One fill model** — backtest, replay, paper, and shadow books all share the same conservative fill semantics (`domain/fills.py`)
- **LLM is explainer only** — never in the decision path; narration polishes recorded reasoning
- **Walk-forward by design** — every mechanism has an ablation shadow book; if removal improves performance, the mechanism is flagged for review (infrastructure in place, runtime wiring in progress — see BETA-DA-4)

## Quick Start

```bash
# Clone
git clone https://github.com/mblaauw/alpha-quant.git
cd alpha-quant

# Install
uv sync

# Configure (create local config with your API keys)
cp config.local.toml.example config.local.toml
# Edit config.local.toml — API keys never leave your machine

# Bootstrap fixtures
uv run alpha-quant bootstrap

# Run tests
uv run pytest
```

## Architecture

Alpha-Quant follows a **ports-and-adapters (hexagonal) architecture** where the domain core has zero I/O and every external dependency is accessed through a port interface with both fake and real adapter implementations.

```mermaid
graph TB
    subgraph Adapters["Adapters (outer ring)"]
        direction TB
        FA["Fake Adapters<br/>fixture_store, virtual_clock,<br/>canned_llm, fixture_market_data,<br/>fixture_fundamentals, fixture_insider,<br/>fixture_sentiment, fake_broker,<br/>fake_event_sink"]
        RA["Real Adapters<br/>eodhd_connector, sec_connector,<br/>openinsider_connector, reddit_connector,<br/>alpaca_connector, llm_adapter,<br/>system_clock, real_event_sink"]
    end

    subgraph Ports["Port Interfaces"]
        P1["Clock"]
        P2["MarketData"]
        P3["Fundamentals"]
        P4["InsiderFeed"]
        P5["SentimentFeed"]
        P6["Store"]
        P7["Broker"]
        P8["EventSink"]
        P9["LLM"]
    end

    subgraph Domain["Domain Core (zero I/O)"]
        M["Models: Position, Candidate,<br/>Decision, Bar, Fill, Order"]
        R["Risk: stops, trails, takes,<br/>drawdown, daily loss"]
        S["Sizing: kelly-lite, risk parity"]
        E["Events: domain event types,<br/>event logging"]
        I["Invariants: I1–I11 checks"]
        D["Derive: incremental indicators<br/>(numpy, O(1) recurrence)"]
        DEC["Mechanisms: M1 universe, M2 regime,<br/>M3 technical, M4 quality,<br/>M5 insider, M6 crowding,<br/>M7 blackout, M8 ranking"]
    end

    subgraph App["Application Services"]
        PL["Pipeline: daily orchestration"]
        BT["Backtest: event-driven simulator"]
        PP["PaperPortfolio: position mgmt"]
        SH["ShadowBook: ablation books"]
        RP["Replay: golden replay (stub)"]
        LB["CLI: run, backtest, journal,<br/>ask, report, status, halt"]
        ST["Store: canonical schema,<br/>DuckDB state persistence"]
        DSH["Dashboard: Streamlit UI"]
    end

    Adapters -->|implement| Ports
    Ports -->|used by| Domain
    App -->|uses| Ports
    App -->|imports| Domain
    Ports -.->|no dependency| App
    Domain -.->|no imports from outside| Ports
```

### Layer Rules

| Layer | Can Import | Cannot Import |
|-------|-----------|---------------|
| `domain/` | Python stdlib, numpy, pydantic | `app/`, `adapters/`, `ports/` |
| `ports/` | `domain/` (types only) | `adapters/`, `app/` |
| `adapters/` | `ports/`, `domain/` (types only) | `app/` |
| `app/` | `domain/`, `ports/` | — |

### Decision Mechanisms (M1–M8)

| ID | Mechanism | Domain Logic | Runtime Wiring | Notes |
|----|-----------|:------------:|:--------------:|-------|
| **M1** | Universe | ✅ Implemented | ❌ Not wired | `universe.select` exists in `domain/`; pipeline uses static config list |
| **M2** | Regime | ✅ Implemented | ⚠️ Partial | SPY EMA50/200 path live; VIX/breadth use hardcoded defaults |
| **M3** | Technical | ✅ Implemented | ✅ Wired | Trend, RSI (Gaussian 52±22), MACD, volume, ATR |
| **—** | Momentum | ✅ Implemented | ✅ Wired | 63-day (~3-month) lookback, bucketed score |
| **M4** | Quality | ✅ Implemented | ✅ Wired | Fundamental gate (operating cash flow, D/E, accruals) |
| **M5** | Insider | ✅ Implemented | ✅ Wired | Buy cluster boost; c-suite sell penalty (.05 per sell, max .30) |
| **M6** | Crowding | ✅ Implemented | ✅ Wired | 14-day block on z>3; configurable via `_BLOCK_DAYS` |
| **M7** | Blackout | ✅ Implemented | ✅ Wired | 3-day pre-earnings entry block |
| **M8** | Composite | ✅ Implemented | ✅ Wired | 0.6·technical + 0.25·momentum + 0.15·insider; equal-weight sector cap (25% of slots) |

> Each mechanism's runtime path is verified by pipeline behavioral tests (426 tests). See [BETA-DA-8](https://github.com/mblaauw/alpha-quant/issues/334).

## CLI Commands

| Command | Status | Description |
|---------|--------|-------------|
| `alpha-quant bootstrap` | ✅ Ready | Generate deterministic fixture data for development |
| `alpha-quant replay` | 🔧 Partial | Golden replay — metadata only; DAG wiring tracked in BETA-DA-2 |
| `alpha-quant ingest` | ✅ Ready | Fetch live data from APIs into canonical store (store-only source) |
| `alpha-quant run` | ✅ Ready | Daily pipeline — reads canonical store (store-only; ingest separately) |
| `alpha-quant backtest` | ✅ Ready | Event-driven backtester (single fill model) |
| `alpha-quant journal` | ✅ Ready | Daily journal with LLM narration |
| `alpha-quant ask` | ✅ Ready | Query recorded decisions and events |
| `alpha-quant report` | ✅ Ready | Weekly/monthly reports (from DB or latest snapshot) |
| `alpha-quant status` | ✅ Ready | Full system status (portfolio, equity, positions, risk) |
| `alpha-quant halt` | ✅ Ready | Halt or resume pipeline |

## Documentation

| Document | Description |
|----------|-------------|
| [Design Specification](DESIGN.md) | Full system design (v1.2) |
| [Architecture Diagrams](docs/architecture/README.md) | C4 model (LikeC4 DSL) |
| [ADR Log](docs/adr/README.md) | 28 Architecture Decision Records |
| [Concept Cards](alpha_quant/concepts/) | 22 mechanism descriptions (ablation, ATR, crowding, momentum, etc.) |
| [GitHub Issues](https://github.com/mblaauw/alpha-quant/issues) | Active backlog — prioritised by P0–P3 |
| [Roadmap](docs/planning/ROADMAP.md) | Beta release status and known limitations |

## Development

```bash
make check          # Ruff lint
make format         # Ruff format
make type           # Type check (ty)
make bootstrap      # Generate fixtures
uv run pytest       # Run tests (419 passing)
make bless-golden   # Update golden replay fixture hash
```

## Configuration

API keys and secrets are **never committed** to the repository. Use one of:

1. **`config.local.toml`** (recommended for local dev) — gitignored, merged on top of `config.toml`
2. **Environment variables** — `ALPHA_QUANT_EODHD__API_KEY=...` (takes highest precedence)

See [config.local.toml.example](config.local.toml.example) for available options.

## Tech Stack

| Component | Choice |
|-----------|--------|
| Runtime | Python 3.14 |
| Package manager | uv |
| Config | pydantic-settings + TOML |
| Domain models | Pydantic v2 (frozen) |
| Indicators | numpy (incremental O(1)) |
| Analytical SQL | DuckDB |
| Columnar storage | pyarrow (Parquet, zstd) |
| HTTP | httpx + tenacity retry |
| Logging | structlog (JSON) |
| Testing | pytest + hypothesis |
| Linting | ruff (lint + format) |
| Type checking | ty (astral) |

## License

MIT

<div align="center">

<div align="center">
  <img src="docs/assets/logo.png" alt="Alpha-Quant Logo" width="200">
</div>

# Alpha-Quant

Deterministic strategy-policy and paper-trading engine

[![CI](https://github.com/mblaauw/alpha-quant/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/mblaauw/alpha-quant/actions)
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://python.org)
[![ty checked](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

</div>

---

## Overview

Alpha-Quant is a deterministic strategy-policy and paper-trading engine. It consumes point-in-time market facts **exclusively from Alpha-Lake** through a versioned authenticated REST API.

Alpha-Quant owns decisions, portfolio controls, paper execution, journals, operational commands, and replay — not market data. Its operational console, **Alpha-Quant Desk**, is a same-origin vanilla JavaScript SPA served by FastAPI with no build toolchain.

**It does not:**
- Ingest market data from any provider
- Calculate technical indicators (RSI, MACD, ATR, moving averages)
- Normalize fundamentals or compute financial ratios
- Scrape sentiment or aggregate mentions
- Manage source-provider connections or API keys
- Maintain a market-data warehouse or Parquet datasets

All neutral market facts come from Alpha-Lake's PIT (point-in-time) API. Every decision, backtest, and replay run is bounded by an explicit `as_of` timestamp and optional `snapshot_id` for deterministic reproducibility.

### Advice Workflow

Alpha-Quant's advice workflow produces daily scorecards with deterministic recommendations:

- **Scorecard engine** converts facts-bundle data into 13 scored components (technical trend, momentum, fundamentals, event risk, etc.) with pass/warn/fail gates and a weighted total score.
- **LLM explanation layer** converts scorecards into structured natural-language advice. The LLM explains deterministic results — it never computes prices, stops, or position sizes.
- **Advice Desk tab** displays daily advice cards with Follow/Modify/Reject actions. Every override is a durable audited command.
- **Risk methods** are user-visible, deterministic policies (fixed percent, ATR trailing, time stop, drawdown ladder, etc.) registered in `METHOD_REGISTRY`.

## Architecture

```
Alpha-Lake owns facts.  Alpha-Quant owns decisions.
```

```
┌──────────────────────────────────────────────┐
│              Alpha-Lake REST API              │
│  /v1/contract  /v1/decision-panel  /v1/univ… │
│  /v1/bars  /v1/indicators  /v1/fundamentals  │
│  /v1/insider-transactions  /v1/earnings-cal…  │
│  /v1/attention-metrics  /v1/trading-calendar  │
└──────────────────────┬───────────────────────┘
                       │
               ┌───────┴───────┐
               │ AlphaLakeRest  │
               │   Client       │
               └───────┬───────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    Decision      Portfolio    Paper
    Context         & Risk    Execution
    Assembly     Constraints   Engine
          │            │            │
          └────────────┼────────────┘
                       ▼
               ┌───────────────┐
               │   PostgreSQL   │
               │  Operational   │
               │     Store      │
               │ (decisions,    │
               │  orders,       │
               │  fills,        │
               │  positions,    │
               │  journal,      │
               │  commands,     │
               │  artifacts)    │
               └───────┬───────┘
                       │
               ┌───────┴───────┐
               │ Alpha-Quant   │
               │    Desk       │
               │ (FastAPI BFF) │
               │  /v1/console  │
               │  /v1/commands │
               └───────────────┘
```

### Key Principles

- **Deterministic** — same config + same Alpha-Lake snapshot = same decisions, every run
- **Fail closed** — when Alpha-Lake is unavailable, stale, or incompatible, the system halts; no silent fallback
- **One fill model** — backtest, replay, and paper books all share the same conservative fill semantics
- **Auditable** — every decision records its Alpha-Lake snapshot_id, facts_hash, config_hash, and provenance
- **Command-only mutations** — all operator writes are durable, idempotent commands; no direct state mutation

## Quick Start

```bash
# Requires a running PostgreSQL and Alpha-Lake server
export ALPHA_LAKE_API_KEY="your-key"

# Seed default reference data (strategies, books, fixtures)
alpha-quant db-dev-seed

# Start the operational console
alpha-quant dashboard
# Open http://localhost:8501

# Seed production reference data
alpha-quant db-seed

# Run background command worker
alpha-quant worker
```

## Commands

| Command | Purpose |
|---------|---------|
| `dashboard` | Launch Alpha-Quant Desk operational console (port 8501) |
| `worker` | Run background command worker process |
| `db-health` | Check PostgreSQL operational store connectivity |
| `db-migrate` | Run Alembic schema migrations |
| `db-migrate-check` | Check pending schema migrations |
| `db-seed` | Seed default reference data |
| `db-dev-seed` | Seed development fixture data |
| `db-import` | Import legacy DuckDB data into PostgreSQL |

## Alpha-Quant Desk

The operational console is a static vanilla JavaScript SPA served by FastAPI, styled as a calm Financial-Times-inspired operational desk.

**Screens:**

| Tab | Purpose |
|-----|---------|
| Advice | Daily advice cards with Follow/Modify/Reject |
| Portfolio | Current book equity, cash, exposures, positions |
| Decisions | Candidates, policy evaluations, ranking, exclusions |
| Orders | Order intent, fill trace, execution history |
| Risk | Halt status, VaR/ES, posture, breaches, component VaR |
| System | Operational dependencies, runs, journal, configuration |

All mutations use authenticated, idempotent, audited commands. The browser never talks directly to PostgreSQL or Alpha-Lake.

## Repo Structure

```
src/alpha_quant/
├── contracts/          # Data contracts (frozen dataclasses)
├── domain/             # Domain models (pydantic FrozenModel)
│   ├── advice.py       # AdviceArtifact, AdviceRecommendation
│   ├── risk.py         # RiskPolicy, RiskDecision, RiskCalculation
│   ├── scorecard.py    # Scorecard, ScorecardComponent
│   └── categories.py   # M1-M8 category mapping
├── ports/              # Port interfaces (AlphaLakeReadPort, Clock, LLM, OperationalStorePort)
├── adapters/
│   ├── postgres/       # PostgreSQL operational store (30+ tables, 7 schemas)
│   ├── real/           # AlphaLakeRestClient, SystemClock, LLM
│   └── fake/           # Fixture-based replay, in-memory fakes (CannedLLM, VirtualClock)
├── application/
│   ├── cli.py          # Typer CLI
│   ├── factory.py      # Composition root
│   ├── daily_cycle.py  # DailyCycleService orchestrator
│   ├── scorecards.py   # Scorecard engine (13 component scorers)
│   ├── advice_llm.py   # LLM explanation layer
│   ├── config.py       # pydantic-settings (TOML + env)
│   ├── commands/       # Command dispatch and 18+ handlers
│   ├── query/          # Console read model services
│   └── risk/           # Risk engine (VaR, component VaR, factors, limits, methods)
├── transport/
│   ├── app.py          # FastAPI application
│   ├── console_routes.py  # /v1/console/* operational read API
│   ├── commands.py     # /v1/commands mutation API
│   ├── health.py       # /livez /readyz health checks
│   ├── deps.py         # Shared FastAPI dependencies
│   └── static/         # Vanilla JS SPA (no build)
│       ├── index.html  # Shell with top bar + tabs
│       ├── styles.css  # CSS token system
│       ├── components/ # Reusable UI primitives
│       └── render/     # Screen views
└── migrations/         # Alembic schema migrations (11 revisions)
```

## Documentation

- [Architecture Decision Records](docs/adr/README.md) — 55 ADRs + 1 archived covering every architectural decision
- [Reference Architecture](docs/architecture/REFERENCE_ARCHITECTURE.md) — System design and key decisions
- [C4 Architecture Diagrams](docs/architecture/README.md) — Context, container, and component views

## License

MIT

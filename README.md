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
- **One fill model** — backtest, replay, paper, and shadow books all share the same conservative fill semantics
- **Ablation-ready** — every mechanism has a shadow book counterpart for walk-forward validation
- **Auditable** — every decision records its Alpha-Lake snapshot_id, metric IDs, and provenance
- **Command-only mutations** — all operator writes are durable, idempotent commands; no direct state mutation

## Quick Start

```bash
# Requires a running Alpha-Lake server
export ALPHA_LAKE_API_KEY="your-key"

# Run the daily decision pipeline
alpha-quant run --as-of 2026-06-24T20:00:00Z --snapshot-id market-close-2026-06-24

# Start the operational console
alpha-quant dashboard
# Open http://localhost:8501

# View status and portfolio
alpha-quant status
```

## Commands

| Command | Purpose |
|---------|---------|
| `run` | Execute daily decision pipeline against Alpha-Lake |
| `dashboard` | Launch Alpha-Quant Desk operational console (port 8501) |
| `worker` | Run background command worker process |
| `status` | Show system and portfolio status |
| `journal` | View decision journal |
| `ask` | Query recorded decisions with LLM |
| `report` | Generate performance report |
| `halt` | Manage system halt |
| `backup` | Backup local decision/paper state |
| `db-health` | Check PostgreSQL operational store connectivity |
| `db-migrate` | Run Alembic schema migrations |
| `db-seed` | Seed default reference data |
| `db-import` | Import legacy DuckDB data into PostgreSQL |

## Alpha-Quant Desk

The operational console is a static vanilla JavaScript SPA served by FastAPI, styled as a calm Financial-Times-inspired operational desk.

**Screens:**

| Tab | Purpose |
|-----|---------|
| Desk | Operational readiness, latest run, attention queue |
| Portfolio | Current book equity, cash, exposures, positions |
| Decisions | Candidates, policy evaluations, ranking, exclusions |
| Orders | Order intent, fill trace, execution history |
| Risk | Halt status, risk posture, breaches, remediation |
| Runs | Decision runs, backtests, replays, commands |
| Journal | Immutable timeline of all system events |
| System | Operational dependencies and configuration |

All mutations use authenticated, idempotent, audited commands. The browser never talks directly to PostgreSQL, Alpha-Lake, or object storage.

## Repo Structure

```
src/alpha_quant/
├── contracts/          # Data contracts (frozen dataclasses)
├── domain/
│   ├── decision_context.py   # NeutralObservations → DecisionContext
│   └── policy/               # 7 strategy policy modules
├── ports/              # Port interfaces (AlphaLakeReadPort, OperationalStorePort, ArtifactStorePort)
├── adapters/
│   ├── postgres/             # PostgreSQL operational store (21 tables, 6 schemas)
│   ├── artifacts/            # S3 artifact store
│   ├── real/                 # AlphaLakeRestClient, SystemClock, LLM
│   └── fake/                 # Fixture-based replay, in-memory fakes
├── application/
│   ├── cli.py                # Typer CLI (12+ commands)
│   ├── factory.py            # Composition root
│   ├── pipeline_v2.py        # Daily decision pipeline
│   ├── config.py             # pydantic-settings (TOML + env)
│   ├── commands/             # Command dispatch and handlers
│   ├── query/                # Console read model services
│   └── store/                # CanonicalStore (DuckDB — legacy)
├── transport/
│   ├── app.py                # FastAPI application
│   ├── console_routes.py     # /v1/console/* operational read API
│   ├── commands.py           # /v1/commands mutation API
│   ├── health.py             # /livez /readyz health checks
│   ├── deps.py               # Shared FastAPI dependencies
│   └── static/               # Vanilla JS SPA (no build)
│       ├── index.html        # Shell with top bar + tabs
│       ├── styles.css         # CSS token system
│       ├── components/       # Reusable UI primitives
│       └── render/           # Screen views
└── migrations/        # Alembic schema migrations (PostgreSQL)
```

## Documentation

- [Architecture Decision Records](docs/adr/README.md) — 48 ADRs covering every architectural decision
- [Reference Architecture](docs/architecture/REFERENCE_ARCHITECTURE.md) — System design and key decisions
- [C4 Architecture Diagrams](docs/architecture/README.md) — Context, container, and component views
- [DESIGN.md](DESIGN.md) — Detailed design document

## License

MIT

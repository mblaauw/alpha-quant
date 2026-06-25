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

Alpha-Quant owns decisions, portfolio controls, paper execution, journals, and replay — not market data.

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
               │ Local State   │
               │ (decisions,   │
               │  orders,      │
               │  fills,       │
               │  positions,   │
               │  journal)     │
               └───────────────┘
```

### Key Principles

- **Deterministic** — same config + same Alpha-Lake snapshot = same decisions, every run
- **Fail closed** — when Alpha-Lake is unavailable, stale, or incompatible, the system halts; no silent fallback
- **One fill model** — backtest, replay, paper, and shadow books all share the same conservative fill semantics
- **Ablation-ready** — every mechanism has a shadow book counterpart for walk-forward validation
- **Auditable** — every decision records its Alpha-Lake snapshot_id, metric IDs, and provenance

## Quick Start

```bash
# Requires a running Alpha-Lake server
export ALPHA_LAKE_API_KEY="your-key"

# Run the daily decision pipeline
alpha-quant run --as-of 2026-06-24T20:00:00Z --snapshot-id market-close-2026-06-24

# Backtest against historical PIT data
alpha-quant backtest --from 2024-01-01 --to 2025-12-31 --snapshot-id historical-v1

# Replay a prior decision run
alpha-quant replay --decision-run-id run-20260624-001

# View status and portfolio
alpha-quant status
```

## Commands

| Command | Purpose |
|---------|---------|
| `run` | Execute daily decision pipeline against Alpha-Lake |
| `backtest` | Historical simulation against PIT Alpha-Lake data |
| `replay` | Deterministic replay of a prior decision run |
| `journal` | View decision journal |
| `report` | Generate performance report |
| `status` | Show system and portfolio status |
| `halt` | Manage system halt file |
| `backup` | Backup local decision/paper state |
| `ask` | Query recorded decisions with LLM |

## Repo Structure

```
src/alpha_quant/
├── ports/              # Port interfaces (AlphaLakeReadPort)
├── contracts/          # Data contracts (dataclasses)
├── domain/
│   ├── decision_context.py   # Fact context for policies
│   └── policy/               # Strategy policy modules
├── adapters/
│   ├── real/                  # AlphaLakeRestClient (httpx)
│   └── fake/                  # AlphaLakeHttpFixtureClient (offline replay)
└── app/                      # CLI, config, factory, pipeline
```

## Documentation

- [Architecture Decision Records](docs/adr/README.md) — 36 ADRs covering every architectural decision
- [Reference Architecture](docs/architecture/REFERENCE_ARCHITECTURE.md) — System design and key decisions
- [C4 Architecture Diagrams](docs/architecture/README.md) — Context, container, and component views
- [DESIGN.md](DESIGN.md) — Detailed design document

## License

MIT

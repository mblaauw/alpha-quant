# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the Alpha-Quant project. Each ADR documents an architecturally-significant decision: the context, options considered, decision outcome, and consequences.

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [0001](./0001-use-python-3-14.md) | Use Python 3.14 as the Runtime | Accepted | 2026-06-10 |
| [0002](./0002-use-uv-package-manager.md) | Use uv as the Package Manager | Accepted | 2026-06-10 |
| [0003](./0003-use-ports-and-adapters.md) | Use Ports-and-Adapters (Hexagonal) Architecture | Accepted | 2026-06-10 |
| [0004](./0004-use-argparse-for-cli.md) | Use argparse (stdlib) for the CLI | Accepted | 2026-06-10 |
| [0005](./0005-use-pydantic-settings-toml.md) | Use pydantic-settings + TOML for Configuration | Accepted | 2026-06-10 |
| [0006](./0006-use-duckdb-parquet-analytical-store.md) | Use DuckDB + Parquet for the Analytical Store | Accepted | 2026-06-10 |
| [0007](./0007-use-sqlite-sqlalchemy-core-transactional.md) | Use SQLite WAL + SQLAlchemy Core for Transactional State | Accepted | 2026-06-10 |
| [0008](./0008-use-custom-numpy-indicators.md) | Use Custom numpy Recurrences for Technical Indicators | Accepted | 2026-06-10 |
| [0009](./0009-use-pessimistic-fill-model.md) | Use Custom Pessimistic Fill Model | Accepted | 2026-06-10 |
| [0010](./0010-use-custom-event-driven-backtester.md) | Use Custom Event-Driven Backtester | Accepted | 2026-06-10 |
| [0011](./0011-use-httpx-for-llm-integration.md) | Use Direct httpx (No SDK) for LLM Integration | Accepted | 2026-06-10 |
| [0012](./0012-use-eodhd-as-primary-data-source.md) | Use EODHD as the Primary Market Data Source | Accepted | 2026-06-10 |
| [0013](./0013-use-structlog-structured-logging.md) | Use structlog with JSON Format for Structured Logging | Accepted | 2026-06-10 |
| [0014](./0014-use-streamlit-for-dashboard.md) | Use Streamlit for the Read-Only Dashboard | Accepted | 2026-06-10 |
| [0015](./0015-use-incremental-o1-indicators.md) | Use Incremental O(1) Indicator Engine | Accepted | 2026-06-10 |
| [0016](./0016-use-degrade-dont-block-failure-model.md) | Use Degrade-Don't-Block Data Failure Model | Accepted | 2026-06-10 |
| [0017](./0017-use-golden-replay-ci.md) | Use Golden Replay as the Primary CI Strategy | Accepted | 2026-06-10 |
| [0018](./0018-use-bootstrap-fixture-workflow.md) | Use Bootstrap + Fixture Bundle Developer Workflow | Accepted | 2026-06-10 |
| [0019](./0019-use-astral-tooling-ruff-ty.md) | Use Astral Development Tooling (ruff + ty) | Accepted | 2026-06-10 |
| [0020](./0020-use-duckdb-for-vault-manifest.md) | Use DuckDB for the Vault Manifest (Dual Use) | Proposed | 2026-06-11 |

## Status Meanings

- **Proposed**: Under review, not yet decided
- **Accepted**: Decided and implemented
- **Deprecated**: Still in use but should not be used for new work
- **Superseded**: Replaced by a newer ADR (linked in the status note)

## New ADRs

To propose a new ADR:
1. Copy the MADR template from [adr.github.io/madr](https://adr.github.io/madr/)
2. Create a new file: `NNNN-title-with-kebab-case.md` (zero-padded sequential number)
3. Set status to `Proposed`
4. Submit as a PR

## Related documents

- [Reference Architecture Document](../architecture/REFERENCE_ARCHITECTURE.md)
- [C4 Architecture Diagrams](../architecture/README.md)

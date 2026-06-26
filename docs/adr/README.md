# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the Alpha-Quant project. Each ADR documents an architecturally-significant decision: the context, options considered, decision outcome, and consequences.

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [0001](./0001-use-python-3-14.md) | Use Python 3.14 as the Runtime | Accepted | 2026-06-10 |
| [0002](./0002-use-uv-package-manager.md) | Use uv as the Package Manager | Accepted | 2026-06-10 |
| [0003](./0003-use-ports-and-adapters.md) | Use Ports-and-Adapters (Hexagonal) Architecture | Accepted | 2026-06-10 |
| [0004](./0004-use-argparse-for-cli.md) | Use argparse (stdlib) for the CLI | Superseded | 2026-06-10 |
| [0005](./0005-use-pydantic-settings-toml.md) | Use pydantic-settings + TOML for Configuration | Accepted | 2026-06-10 |
| [0006](./0006-use-duckdb-parquet-analytical-store.md) | Use DuckDB + Parquet for the Analytical Store | **Superseded** | 2026-06-10 |
| [0007](./0007-use-sqlite-sqlalchemy-core-transactional.md) | Use SQLite WAL + SQLAlchemy Core for Transactional State | Superseded | 2026-06-10 |
| [0008](./0008-use-custom-numpy-indicators.md) | Use Custom numpy Recurrences for Technical Indicators | **Superseded** | 2026-06-10 |
| [0009](./0009-use-pessimistic-fill-model.md) | Use Custom Pessimistic Fill Model | Accepted | 2026-06-10 |
| [0010](./0010-use-custom-event-driven-backtester.md) | Use Custom Event-Driven Backtester | Accepted | 2026-06-10 |
| [0011](./0011-use-httpx-for-llm-integration.md) | Use Direct httpx (No SDK) for LLM Integration | Accepted | 2026-06-10 |
| [0012](./0012-use-eodhd-as-primary-data-source.md) | Use EODHD as the Primary Market Data Source | Superseded | 2026-06-10 |
| [0013](./0013-use-structlog-structured-logging.md) | Use structlog with JSON Format for Structured Logging | Accepted | 2026-06-10 |
| [0014](./0014-use-streamlit-for-dashboard.md) | Use Streamlit for the Read-Only Dashboard | **Superseded** | 2026-06-10 |
| [0015](./0015-use-incremental-o1-indicators.md) | Use Incremental O(1) Indicator Engine | **Superseded** | 2026-06-10 |
| [0016](./0016-use-degrade-dont-block-failure-model.md) | Use Degrade-Don't-Block Data Failure Model | Accepted | 2026-06-10 |
| [0017](./0017-use-golden-replay-ci.md) | Use Golden Replay as the Primary CI Strategy | Accepted | 2026-06-10 |
| [0018](./0018-use-bootstrap-fixture-workflow.md) | Use Bootstrap + Fixture Bundle Developer Workflow | **Superseded** | 2026-06-10 |
| [0019](./0019-use-astral-tooling-ruff-ty.md) | Use Astral Development Tooling (ruff + ty) | Accepted | 2026-06-10 |
| [0020](./0020-use-duckdb-for-vault-manifest.md) | Use DuckDB for the Vault Manifest (Dual Use) | Superseded | 2026-06-11 |
| [0021](./0021-use-duckdb-for-both-analytical-and-transactional-state.md) | Use DuckDB for Both Analytical and Transactional State | Accepted | 2026-06-11 |
| [0022](./0022-use-paper-portfolio-engine.md) | Use Paper Portfolio Engine as Authoritative State Manager | Accepted | 2026-06-12 |
| [0023](./0023-use-pipeline-orchestrator.md) | Use Pipeline Orchestrator for Daily Run Sequencing | Accepted | 2026-06-12 |
| [0024](./0024-use-self-consistency-invariants.md) | Use Self-Consistency Invariants for Portfolio Integrity | Accepted | 2026-06-12 |
| [0025](./0025-use-sec-connector-sqlite-cache.md) | Use SQLite Cache for SEC Connector | Superseded | 2026-06-12 |
| [0026](./0026-use-content-addressed-vault.md) | Use Content-Addressed Vault for Raw Data Storage | Superseded | 2026-06-12 |
| [0027](./0027-use-dependency-pruning.md) | Dependency Pruning — polars, SQLAlchemy, APScheduler CLI, 50-Day Prune | Accepted | 2026-06-13 |
| [0028](./0028-use-clock-virtualization-for-determinism.md) | Clock Virtualization for Deterministic Replay | Accepted | 2026-06-15 |
| [0029](./0029-use-store-mixin-decomposition.md) | Store Mixin Decomposition for Schema Organization | Accepted | 2026-06-15 |
| [0030](./0030-use-shadow-ablation-books.md) | Shadow Ablation Books for Mechanism Evaluation | Accepted | 2026-06-15 |
| [0031](./0031-use-file-based-halt-mechanism.md) | File-Based Halt Mechanism for System Safety | **Superseded** | 2026-06-15 |
| [0032](./0032-alpha-lake-data-plane.md) | Alpha-Lake as the Sole Data Plane | **Superseded** | 2026-06-21 |
| [0033](./0033-pit-reads-via-clock-asof.md) | PIT Reads via Clock-Driven `as_of` | Accepted | 2026-06-21 |
| [0034](./0034-lake-gateway-port.md) | LakeGateway Port and Adapters | **Superseded** | 2026-06-21 |
| [0035](./0035-alpha-lake-rest-sole-facts-plane.md) | Alpha-Lake REST Is the Sole Alpha-Quant Runtime Facts Plane | **Accepted** | 2026-06-25 |
| [0036](./0036-neutral-facts-strategy-policy.md) | Neutral Facts in Alpha-Lake, Strategy Policy in Alpha-Quant | **Accepted** | 2026-06-25 |
| [0037](./0037-postgresql-operational-system-of-record.md) | PostgreSQL as the Operational System of Record | **Accepted** | 2026-06-26 |
| [0038](./0038-append-only-ledger-rebuildable-projections.md) | Append-Only Ledger with Rebuildable Projections | **Accepted** | 2026-06-26 |
| [0039](./0039-s3-compatible-artifact-store.md) | S3-Compatible Artifact Store | **Accepted** | 2026-06-26 |
| [0040](./0040-database-backed-halts-transactional-run-locks.md) | Database-Backed Halts and Transactional Run Locks | **Accepted** | 2026-06-26 |
| [0041](./0041-migration-strategy-src-alpha-quant.md) | Migration Strategy — Consolidating to `src/alpha_quant/` | **Accepted** | 2026-06-26 |

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

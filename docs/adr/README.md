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
| [0009](./0009-use-pessimistic-fill-model.md) | Use Custom Pessimistic Fill Model | **Superseded** | 2026-06-10 |
| [0010](./0010-use-custom-event-driven-backtester.md) | Use Custom Event-Driven Backtester | **Superseded** | 2026-06-10 |
| [0011](./0011-use-httpx-for-llm-integration.md) | Use Direct httpx (No SDK) for LLM Integration | Accepted | 2026-06-10 |
| [0012](./0012-use-eodhd-as-primary-data-source.md) | Use EODHD as the Primary Market Data Source | Superseded | 2026-06-10 |
| [0013](./0013-use-structlog-structured-logging.md) | Use structlog with JSON Format for Structured Logging | Accepted | 2026-06-10 |
| [0014](./0014-use-streamlit-for-dashboard.md) | Use Streamlit for the Read-Only Dashboard | Superseded by 0046 | 2026-06-10 |
| [0015](./0015-use-incremental-o1-indicators.md) | Use Incremental O(1) Indicator Engine | **Superseded** | 2026-06-10 |
| [0016](./0016-use-degrade-dont-block-failure-model.md) | Use Degrade-Don't-Block Data Failure Model | Accepted | 2026-06-10 |
| [0017](./0017-use-golden-replay-ci.md) | Use Golden Replay as the Primary CI Strategy | Accepted | 2026-06-10 |
| [0018](./0018-use-bootstrap-fixture-workflow.md) | Use Bootstrap + Fixture Bundle Developer Workflow | **Superseded** | 2026-06-10 |
| [0019](./0019-use-astral-tooling-ruff-ty.md) | Use Astral Development Tooling (ruff + ty) | Accepted | 2026-06-10 |
| [0020](./0020-use-duckdb-for-vault-manifest.md) | Use DuckDB for the Vault Manifest (Dual Use) | Superseded | 2026-06-11 |
| [0021](./0021-use-duckdb-for-both-analytical-and-transactional-state.md) | Use DuckDB for Both Analytical and Transactional State | **Superseded** | 2026-06-11 |
| [0022](./0022-use-paper-portfolio-engine.md) | Use Paper Portfolio Engine as Authoritative State Manager | **Superseded** | 2026-06-12 |
| [0023](./0023-use-pipeline-orchestrator.md) | Use Pipeline Orchestrator for Daily Run Sequencing | **Superseded** | 2026-06-12 |
| [0024](./0024-use-self-consistency-invariants.md) | Use Self-Consistency Invariants for Portfolio Integrity | **Superseded** | 2026-06-12 |
| [0025](./0025-use-sec-connector-sqlite-cache.md) | Use SQLite Cache for SEC Connector | Superseded | 2026-06-12 |
| [0026](./0026-use-content-addressed-vault.md) | Use Content-Addressed Vault for Raw Data Storage | Superseded | 2026-06-12 |
| [0027](./0027-use-dependency-pruning.md) | Dependency Pruning — polars, SQLAlchemy, APScheduler CLI, 50-Day Prune | **Superseded** | 2026-06-13 |
| [0028](./0028-use-clock-virtualization-for-determinism.md) | Clock Virtualization for Deterministic Replay | Accepted | 2026-06-15 |
| [0029](./0029-use-store-mixin-decomposition.md) | Store Mixin Decomposition for Schema Organization | **Superseded** | 2026-06-15 |
| [0030](./0030-use-shadow-ablation-books.md) | Shadow Ablation Books for Mechanism Evaluation | **Superseded** | 2026-06-15 |
| [0031](./0031-use-file-based-halt-mechanism.md) | File-Based Halt Mechanism for System Safety | **Superseded** | 2026-06-15 |
| [0032](./0032-alpha-lake-data-plane.md) | Alpha-Lake as the Sole Data Plane | **Superseded** | 2026-06-21 |
| [0033](./0033-pit-reads-via-clock-asof.md) | PIT Reads via Clock-Driven `as_of` | Accepted | 2026-06-21 |
| [0034](./0034-lake-gateway-port.md) | LakeGateway Port and Adapters | **Superseded** | 2026-06-21 |
| [0035](./0035-alpha-lake-rest-sole-facts-plane.md) | Alpha-Lake REST Is the Sole Alpha-Quant Runtime Facts Plane | **Accepted** | 2026-06-25 |
| [0036](./0036-neutral-facts-strategy-policy.md) | Neutral Facts in Alpha-Lake, Strategy Policy in Alpha-Quant | **Accepted** | 2026-06-25 |
| [0037](./0037-postgresql-operational-system-of-record.md) | PostgreSQL as the Operational System of Record | **Accepted** | 2026-06-26 |
| [0038](./0038-append-only-ledger-rebuildable-projections.md) | Append-Only Ledger with Rebuildable Projections | **Accepted** | 2026-06-26 |
| [0039](./0039-s3-compatible-artifact-store.md) | S3-Compatible Artifact Store | **Superseded** | 2026-06-26 |
| [0040](./0040-database-backed-halts-transactional-run-locks.md) | Database-Backed Halts and Transactional Run Locks | **Accepted** | 2026-06-26 |
| [0041](./0041-migration-strategy-src-alpha-quant.md) | Migration Strategy — Consolidating to `src/alpha_quant/` | **Accepted** | 2026-06-26 |
| [0042](./0042-static-spa-fastapi-bff.md) | Static SPA and Same-Origin FastAPI BFF | **Accepted** | 2026-06-26 |
| [0043](./0043-durable-command-model.md) | Durable Command Model for Dashboard Mutations | **Accepted** | 2026-06-26 |
| [0044](./0044-persistent-docker-volumes.md) | Persistent Named Docker Volumes and Idempotent Migrations | **Accepted** | 2026-06-26 |
| [0045](./0045-no-offline-cache-operational-console.md) | No Offline Cache for the Write-Capable Operational Console | **Accepted** | 2026-06-26 |
| [0046](./0046-static-lake-watch-aligned-console.md) | Static Lake Watch–Aligned Operational Console | **Accepted** | 2026-06-27 |
| [0047](./0047-operational-context-not-global-pit.md) | Operational Context Is Not Global PIT Context | **Accepted** | 2026-06-27 |
| [0048](./0048-commands-sole-mutation-boundary.md) | Commands Are the Sole Mutation Boundary | **Accepted** | 2026-06-27 |
| [0049](./0049-alpha-lake-facts-bundle-consumption.md) | Alpha-Lake Facts Bundle as Primary Scorecard Data Source | Accepted | 2026-06-27 |
| [0050](./0050-scorecards-as-primary-decision-artifact.md) | Scorecards Are the Primary Decision Artifact | Accepted | 2026-06-27 |
| [0051](./0051-llm-explains-deterministic-advice.md) | LLM Explains Deterministic Advice — Never Computes It | Accepted | 2026-06-27 |
| [0052](./0052-user-overrides-as-audited-commands.md) | User Overrides Are Audited Commands | Accepted | 2026-06-27 |
| [0053](./0053-risk-methods-as-user-visible-policy.md) | Risk Methods Are User-Visible Deterministic Policies | Accepted | 2026-06-27 |
| [0054](./0054-evolved-desk-advice-tab.md) | Desk Redesigned with Advice-First Tab | Accepted | 2026-06-27 |
| [0055](./0055-risk-desk-placeholder-contract.md) | Risk Desk Uses a Stable Placeholder Contract Before the Real Risk Engine | Superseded by 0056 | 2026-06-28 |
| [0056](./0056-real-risk-engine.md) | Real Risk Engine Replaces Placeholder Calculations | Accepted | 2026-06-28 |
| [0057](./57-scorecard-engine-as-decision-core.md) | Scorecard Engine Replaces Policy Modules as Decision Core | Accepted | 2026-06-30 |
| [0058](./58-removal-of-cli-run-commands.md) | Removal of CLI run/status/journal/ask/report/halt/backup Commands | Accepted | 2026-06-30 |
| [0059](./59-domainevent-regression-to-dict.md) | DomainEvent Regression to Plain dict | Accepted | 2026-06-30 |
| [0060](./60-risk-engine-synthetic-returns-v1.md) | Risk Engine Uses Synthetic Returns as v1 Methodology | Accepted | 2026-06-30 |
| [0061](./61-duckdb-retained-for-legacy-import.md) | DuckDB Retained for Legacy Import Only | Accepted | 2026-06-30 |
| [0062](./62-console-mutation-routes-reconciled.md) | Console Mutation Routes Reconciled with Command Bus | Accepted | 2026-06-30 |
| [0063](./63-unified-risk-policy-model.md) | Unified Risk Policy Model Replaces Three Disconnected Systems | Accepted | 2026-06-30 |
| [0064](./64-scoring-policy-versioning.md) | Scoring Policy Versioning via RiskPolicy.component_weights_json | Accepted | 2026-06-30 |
| [0065](./65-llm-integration-and-guardrails.md) | LLM Integration and Guardrails for Deterministic Advice | Accepted | 2026-06-30 |
| [0066](./66-fake-operational-store-containerless-testing.md) | FakeOperationalStore Enables Containerless Testing | Accepted | 2026-06-30 |
| [0067](./67-llm-explanation-boundary.md) | LLM Explanation Boundary and Non-Authoritative Role | Accepted | 2026-06-30 |
| [0068](./68-snapshot-based-explanation-invalidation.md) | Calculation-Snapshot-Based Explanation Invalidation | Accepted | 2026-06-30 |
| [0069](./69-structured-output-validation-contract.md) | Structured Output and Validation Contract for Explanations | Accepted | 2026-06-30 |
| [0070](./70-mock-first-llm-provider-strategy.md) | Mock-First LLM Provider Strategy for Explanations | Accepted | 2026-06-30 |
| [0071](./71-explanation-persistence-and-provenance.md) | Explanation Persistence and Provenance | Accepted | 2026-06-30 |

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

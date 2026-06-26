# Adapter Reference

## Port → Implementation Matrix

| Port | Interface | Real Adapter | Fake Adapter |
|------|-----------|--------------|--------------|
| AlphaLakeReadPort | read_observations(), health(), contract() | AlphaLakeRestClient (httpx → Alpha-Lake REST API) | AlphaLakeHttpFixtureClient (pre-recorded JSON fixtures) |
| OperationalStorePort | 20 methods (reserve_run, start_run, complete_run, commit_decision_batch, book_fill, load_portfolio, set_halt, clear_halt, rebuild_projections, list_decision_runs, etc.) | PostgresOperationalStore (SQLAlchemy Core + psycopg) | FakeOperationalStore (in-memory dict) |
| ArtifactStorePort | put_json, get_json, verify | S3ArtifactStore (boto3, SHA-256 checksums) | (none) |
| Store (legacy) | 6 mixin interfaces (PositionStore, OrderStore, DecisionStore, EventStore, JournalStore, AdminStore) | CanonicalStore (DuckDB) | FixtureStore (in-memory) |
| Clock | now, today, market_date | SystemClock (datetime.now(UTC)) | VirtualClock (deterministic) |
| EventSink (legacy) | emit, query | DuckDBEventSink | FakeEventSink |
| LLM | explain, generate_card | OpenAILikeLLM (OpenAI-compatible API via httpx) | CannedLLM (static templates) |

---

## AlphaLakeReadPort — The Facts Plane

All market facts enter through a single port (`ports/alpha_lake.py`). Every read is a point-in-time query clock-driven by `as_of` — the pipeline never ingests raw data directly.

| Method | Returns | Purpose |
|--------|---------|---------|
| `health()` | `bool` | GET /v1/health |
| `contract()` | `LakeContract` | GET /v1/contract — version negotiation |
| `read_universe()` | `list[SecurityMasterEntry]` | GET /v1/universe |
| `read_observations()` | `NeutralObservations` | GET /v1/decision-panel → parsed into PriceObservation, TechnicalObservations, SymbolObservations, MarketObservations |
| `read_decision_panel()` | `DecisionPanel` | Legacy — backward compat |
| `read_replay_panel()` | `ReplayPanel` | Legacy — backward compat |

### Real Adapter: AlphaLakeRestClient

`adapters/real/alpha_lake_rest.py` — connects to the Alpha-Lake REST API via **httpx**.

- API key authentication via `X-API-Key` header
- Connection pooling with configurable limits
- Timeout configuration (connect, read, write, pool)
- JSON response parsing into domain-typed Pydantic models
- Error handling with structured error responses

### Fake Adapter: AlphaLakeHttpFixtureClient

`adapters/fake/alpha_lake_fixtures.py` — reads pre-recorded JSON fixtures from `fixtures/{version}/` subdirectory.

- Fixtures stored as JSON files keyed by endpoint + request parameters
- Deterministic PIT replay — no network dependency
- Same return types as the real adapter

---

## OperationalStorePort — State Management

`ports/operational_store.py` — the single write port for all pipeline state. A PostgresOperationalStore backed by 6 schemas:

| Schema | Tables |
|--------|--------|
| **core** | strategy, strategy_version, portfolio_book, security_reference, execution_profile |
| **run** | decision_run, candidate_evaluation, policy_evaluation, alpha_lake_manifest |
| **trade** | paper_order, paper_fill, cash_ledger_entry, corporate_action_booking, portfolio_mark |
| **projection** | position_current, portfolio_current |
| **audit** | audit_event, risk_event, halt_transition |
| **ops** | current_halt, run_lock_audit |

### Real Adapter: PostgresOperationalStore

`adapters/real/postgres_operational_store.py` — SQLAlchemy Core + psycopg.

- Write path is append-only (ledger semantics) with rebuildable projections
- Unit of Work pattern wraps commit/rollback via `OperationalUnitOfWork`
- Projections (`position_current`, `portfolio_current`) rebuilt on demand via `rebuild_projections()`
- Alembic-managed schema migrations (`run_migrations`)

### Fake Adapter: FakeOperationalStore

`adapters/fake/fake_operational_store.py` — in-memory dict store for tests.

- Same method signatures as `PostgresOperationalStore`
- No persistence across test runs

---

## S3ArtifactStore — Decision Evidence

`ports/artifact_store.py` — stores decision artifacts for audit and post-hoc analysis.

| Method | Purpose |
|--------|---------|
| `put_json(run_id, symbol, decision_id, data)` | Write artifact with SHA-256 checksum |
| `get_json(run_id, symbol, decision_id)` | Read artifact by key |
| `verify(run_id, symbol, decision_id)` | Verify checksum integrity |

**Layout:**
- Bucket: `alpha-quant-artifacts`
- Key pattern: `{run_id}/{symbol}/{decision_id}.json`
- SHA-256 checksums stored in S3 metadata (`x-amz-meta-sha256`)
- Fire-and-forget write during pipeline run
- Read-only during post-hoc analysis

### Real Adapter: S3ArtifactStore

`adapters/real/s3_artifact_store.py` — boto3 with configurable endpoint (AWS S3 or S3-compatible).

---

## Legacy Adapters

These adapters remain functional but are being phased out:

| Adapter | Replaced By | Status |
|---------|-------------|--------|
| **CanonicalStore** (DuckDB) | PostgresOperationalStore | Active but legacy — new code targets PostgreSQL |
| **DuckDBEventSink** | audit_event table in PostgresOperationalStore | Active but legacy — events migrate to audit schema |
| **InProcessLakeGateway** | AlphaLakeRestClient | Removed — replaced by REST-based AlphaLakeReadPort |
| **FixtureLakeGateway** | AlphaLakeHttpFixtureClient | Removed — replaced by fixture-based AlphaLakeReadPort |
| **RestLakeGateway** | AlphaLakeRestClient | Removed — never shipped; superseded by AlphaLakeReadPort |
| **LakeMarketData / LakeFundamentals / LakeInsiderFeed / LakeSentimentFeed** | AlphaLakeReadPort | Removed — per-domain wrappers consolidated into single port |

---

## Wiring (factory.py)

```python
create_alpha_lake_reader → AlphaLakeRestClient (live) / AlphaLakeHttpFixtureClient (fixture)
create_event_sink        → DuckDBEventSink (live) / FakeEventSink (fixture)
create_store             → CanonicalStore (live) / FixtureStore (fixture)
create_llm               → OpenAILikeLLM (live) / CannedLLM (fixture)
create_clock             → SystemClock (live) / VirtualClock (fixture)
create_unit_of_work      → OperationalUnitOfWork (PostgreSQL) — always
run_migrations           → Alembic upgrade to head
seed_default_data        → Insert default strategy + portfolio_book
```

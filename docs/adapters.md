# Adapter Reference

## Port → Implementation Matrix

| Port | Interface | Real Adapter | Fake Adapter |
|------|-----------|--------------|--------------|
| AlphaLakeReadPort | health(), contract(), get_freshness(), read_facts_bundle(), list_symbols(), add_symbol(), remove_symbol(), close() | AlphaLakeRestClient (httpx → Alpha-Lake REST API) | AlphaLakeHttpFixtureClient (pre-recorded JSON fixtures) |
| OperationalStorePort | 33 methods (reserve_run, start_run, complete_run, commit_decision_batch, book_fill, load_portfolio, save_portfolio_mark, save_scorecard, load_scorecard, load_scorecards_for_run, save_advice_artifact, load_advice_artifacts, mark_explanations_stale, set_halt, clear_halt, current_halt, rebuild_projections, list_strategies, list_books, list_decision_runs, get_run_by_key, list_candidates, list_policy_evals, list_audit_events, list_positions, load_risk_policy, save_risk_policy_version, write_risk_event, write_corporate_action_booking, write_run_lock_audit, submit_command, get_command, get_command_by_idempotency, list_commands, queue_command, claim_command, complete_command, create_order, cancel_order, update_position_stop, set_book_risk_profile, update_position_risk, list_risk_methods, config_set, mark_operator_excluded) | PostgresOperationalStore (SQLAlchemy Core + psycopg) | FakeOperationalStore (in-memory dict) |
| Clock | now, today, market_date | SystemClock (datetime.now(UTC)) | VirtualClock (deterministic) |
| LLM | explain, generate_card | OpenAILikeLLM (OpenAI-compatible API via httpx) | CannedLLM (static templates with explanation fixtures) |

---

## AlphaLakeReadPort — The Facts Plane

All market facts enter through a single port (`ports/alpha_lake.py`). Every read is a point-in-time query clock-driven by `as_of` and optionally pinned to a `snapshot_id` — the pipeline never ingests raw data directly.

| Method | Returns | Purpose |
|--------|---------|---------|
| `health()` | `AlphaLakeHealth` | GET /v1/health |
| `contract()` | `AlphaLakeContract` | GET /v1/contract — version negotiation |
| `get_freshness(symbols)` | `dict[str, datetime]` | GET /v1/freshness — staleness per symbol |
| `read_facts_bundle(symbol, as_of, ...)` | `FactsBundle` | GET /v1/facts — parsed into observation categories |
| `list_symbols(active_only)` | `list[SymbolRegistryItem]` | GET /v1/symbols — universe registry |
| `add_symbol(symbol)` | `SymbolMutationResult` | PUT /v1/symbols — register new symbol |
| `remove_symbol(symbol)` | `SymbolMutationResult` | DELETE /v1/symbols — unregister symbol |
| `close()` | `None` | Release HTTP connection pool |

### Real Adapter: AlphaLakeRestClient

`adapters/real/alpha_lake_rest.py` — connects to the Alpha-Lake REST API via **httpx**.

- API key authentication via `X-API-Key` header
- Connection pooling with configurable limits
- Timeout configuration (connect, read, write, pool)
- JSON response parsing into domain-typed Pydantic models
- Error handling with structured error responses

### Fake Adapter: AlphaLakeHttpFixtureClient

`adapters/fake/alpha_lake_http_fixture.py` — reads pre-recorded JSON fixtures from `fixtures/{version}/` subdirectory.

- Fixtures stored as JSON files keyed by endpoint + request parameters
- Deterministic PIT replay — no network dependency
- Same return types as the real adapter

---

## OperationalStorePort — State Management

`ports/operational_store.py` — the single write port for all pipeline state. A PostgresOperationalStore backed by 6 schemas:

| Schema | Tables |
|--------|--------|
| **core** | strategy, strategy_version, portfolio_book, security_reference, execution_profile |
| **run** | decision_run, candidate_evaluation, policy_evaluation, alpha_lake_manifest, scorecard, scorecard_component, advice_artifact |
| **trade** | paper_order, paper_fill, cash_ledger_entry, corporate_action_booking, portfolio_mark |
| **projection** | position_current, portfolio_current |
| **audit** | audit_event, risk_event, halt_transition, operator_override |
| **ops** | current_halt, run_lock_audit, command, app_config |

### Real Adapter: PostgresOperationalStore

`adapters/postgres/operational_store.py` — SQLAlchemy Core + psycopg.

- Write path is append-only (ledger semantics) with rebuildable projections
- Unit of Work pattern wraps commit/rollback via `OperationalUnitOfWork`
- Projections (`position_current`, `portfolio_current`) rebuilt on demand via `rebuild_projections()`
- Alembic-managed schema migrations (`run_migrations`)

### Fake Adapter: FakeOperationalStore

`adapters/fake/operational_store.py` — in-memory dict store for tests.

- Same method signatures as `PostgresOperationalStore`
- No persistence across test runs

---

## Wiring (factory.py)

```python
create_alpha_lake_reader → AlphaLakeRestClient (rest) / AlphaLakeHttpFixtureClient (fixture)
create_llm               → OpenAILikeLLM (live) / CannedLLM (fixture)
create_clock             → SystemClock (live) / VirtualClock (fixture)
create_unit_of_work      → OperationalUnitOfWork (postgres) / FakeUnitOfWork (fake)
run_migrations           → Alembic upgrade to head
seed_default_data        → Insert default strategy + portfolio_book
```

# ADR-0022: Use Paper Portfolio Engine as Authoritative State Manager

## Status

Accepted

## Date

2026-06-12

## Context

Alpha-Quant is an internal paper-trading system with no broker dependency (per DESIGN.md §9). All execution is simulated: the system decides at T close, fills at T+1 open, and tracks positions, cash, and equity internally. This requires an authoritative state manager that can:

1. Track cash, positions, orders, fills, and equity curve across daily runs
2. Execute the same fill model as backtesting and replay (I8)
3. Persist state transactionally and recover after restart
4. Support self-consistency checks (I12)

During Phase 2 implementation, two approaches emerged:
- A stateless functional approach where the pipeline re-computes state from events
- A stateful `PaperPortfolio` class that wraps a `Store` and manages cash/positions in-memory with periodic snapshots

## Decision Drivers

- **Deterministic recovery** — After restart, portfolio state must be recoverable from the Store (cash, positions, last equity curve point)
- **Single state authority** — One class manages all portfolio mutations, reducing the risk of inconsistent updates
- **Transactional writes** — All portfolio state changes within a single pipeline run should be atomic
- **Fill model reuse** — The paper portfolio must use the same `fill_entry_order`, `fill_stop_loss`, and `fill_partial_take` functions as the backtester
- **Testability** — Must work with both `FixtureStore` (in-memory for tests) and `CanonicalStore` (DuckDB for production)

## Considered Options

- **Option A: PaperPortfolio class (current choice)** — A class wrapping `Store` with in-memory cash tracking, methods for initialize/process_risk_actions/process_entry_orders/mark_to_market/self_consistency_check
- **Option B: Stateless pipeline functions** — Each pipeline run re-computes cash from events/decisions, no dedicated state class
- **Option C: Event-sourced portfolio** — Every state change is an event; current state is computed by replaying all events since epoch

## Decision Outcome

Chosen option: **Option A — PaperPortfolio class**.

Rationale:
1. In-memory cash tracking is simpler and faster than event replay for every operation
2. `PortfolioSnapshot` model in the Store provides deterministic recovery after restart
3. The class encapsulates all portfolio mutation logic, making it a single point of authority
4. `self_consistency_check()` delegates to `check_invariants()` for I1/I5/I6 enforcement

### Positive Consequences

- Clear separation: PaperPortfolio owns state, pipeline owns sequencing
- Recoverable: `load_latest_portfolio_snapshot()` restores cash on instantiation
- Testable: FixtureStore backed by real in-memory dicts for orders/fills/positions/events/snapshots
- Event emission: PaperPortfolio emits `FillBooked`, `OrderSimulated`, `PartialTaken` for audit trail

### Negative Consequences

- Dual state management: cash in-memory + PortfolioSnapshot in Store — could diverge if either is buggy
- Not purely functional: PaperPortfolio has mutable `_cash` state, requiring careful ordering of operations
- The backtester does not use PaperPortfolio (P1.5/P2.3 in refinement backlog) — two state managers exist

## References

- DESIGN.md §9: Internal paper-trading engine
- ADR-0009: Pessimistic fill model
- `src/app/paper.py`
- `src/domain/invariants.py`
- `src/domain/models.py` — `PortfolioSnapshot`
- `src/ports/store.py` — `save_portfolio_snapshot`, `load_latest_portfolio_snapshot`

# ADR-0003: Use Ports-and-Adapters (Hexagonal) Architecture

## Status

Accepted

## Date

2026-06-10

## Context

Alpha-Quant operates in three execution realities (backtest, replay, paper trading) with seven external data sources and an LLM provider. The domain logic (decision engine, risk management, fill model) must be pure, testable, and independent of infrastructure. The system must support swapping data sources (e.g., Tiingo → fixture for replay, real → fake for CI).

The DESIGN.md §1 mandates: "domain/ imports nothing from adapters/ or data/. Every connector has a fixture-backed fake twin on the same port. The pipeline never knows which reality it runs in."

## Decision Drivers

- Domain purity: trading logic must be testable without network calls or real data
- Three execution realities: backtest, replay, paper — same domain code, different adapters
- Seven data sources: each must have a fake twin for deterministic testing
- LLM is explainer-only: the narration path must be independently testable from the decision path
- Future-proofing: broker execution will be added later without touching domain code

## Considered Options

- **Option A: Ports-and-Adapters (Hexagonal)** — Abstract port interfaces (Python ABCs/Protocols), domain depends on ports only; adapters implement ports
- **Option B: Traditional Layered Architecture** — Single dependency direction (Controller → Service → Repository), but tighter coupling between layers
- **Option C: Clean Architecture (Uncle Bob)** — Similar to ports-and-adapters but with more rigid layer rules; overkill for the project's scale

## Decision Outcome

Chosen option: **Option A — Ports-and-Adapters (Hexagonal)**.

Rationale:
1. Enforces the 13 system invariants (I1–I13) at the structural level — domain cannot accidentally import an adapter
2. Every connector having a fake twin is not a nice-to-have but a necessity for deterministic golden replay
3. The three execution realities (backtest, replay, paper) are exactly the use case this pattern was designed for
4. Simple to implement with Python ABCs — no framework required
5. The broker port (DESIGN §9.4) is a natural extension: defined now, implemented later, domain untouched

### Positive Consequences

- Domain code is pure functions with no side effects — trivially unit-testable
- CI uses fake adapters only — no API keys, no network, no flaky tests
- New data sources can be added by implementing the port interface
- The golden replay CI (I7) compares outputs at the port boundaries

### Negative Consequences

- More interfaces to define upfront (9 ports in P0.2)
- Slightly more indirection than calling APIs directly (but the testing benefit outweighs this)
- Requires import-linter discipline (`ruff` rules or manual review to prevent domain → adapter imports)

## References

- DESIGN.md §1 (Architecture overview), §16 (System invariants)
- RAD §5 (Container Architecture), §6.1 (Data Layer Components)
- C4 Container diagram: `docs/architecture/views/container.png`

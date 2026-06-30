# ADR-0023: Use Pipeline Orchestrator for Daily Run Sequencing

## Status

Superseded by ADR-0048 (Command Bus + DailyCycleService).

## Date

2026-06-12

## Context

The daily run sequence (DESIGN.md §13) requires coordinating multiple domain functions in order: load data → derive indicators → detect regime → evaluate risk → score/rank/size candidates → persist decisions. During Phase 2, three consumers of this sequence emerged:

1. **`app/backtest.py`** — Historical simulation over a date range
2. **`app/pipeline.py`** — Single-day live execution
3. **`app/paper.py`** — Portfolio state management (called by pipeline)

Each implementation independently solved the same coordination problem (bar loading, indicator updates, scoring loops) leading to significant code duplication (~40% shared logic between backtest.py and pipeline.py).

## Decision Drivers

- **One daily sequence** — The order of operations (ingest → derive → regime → risk → decide → order → fill → persist) must be the same across all execution realities (I8)
- **Event emission** — Every stage emits typed domain events for audit, narration, and debugging
- **Degradation tolerance** — Connector failure emits `SourceDegraded` but does not halt the sequence
- **Dependency injection** — The pipeline must work with real connectors (live), fixture adapters (CI), and test doubles (unit tests)
- **Single-day scope** — The pipeline operates on one day at a time; the scheduler (APScheduler/system cron) handles repetition

## Considered Options

- **Option A: Separate backtest + pipeline modules (current choice)** — `app/backtest.py` for historical runs, `app/pipeline.py` for single-day runs, `app/paper.py` for state management
- **Option B: Unified orchestrator** — One module that handles both single-day and multi-day runs with a date-range parameter
- **Option C: Pipeline as library** — Pipeline functions called by both a CLI `run` command and a backtest loop

## Decision Outcome

Chosen option: **Option A (with Option C planned for P1.6 refinement)**.

Rationale:
1. The backtest and pipeline have fundamentally different output requirements: backtest produces `BacktestResult` (equity curve, metrics), pipeline produces `RunResult` (events, violations)
2. Keeping them separate allows each to evolve independently without breaking the other
3. Option C (extracting shared loop utilities) is planned as P1.6 to address the 40% code duplication

### Positive Consequences

- Clear separation of concerns: backtest = multi-day research, pipeline = single-day production
- `PipelineResult` captures events, decisions, and violations for the daily journal
- Degradation handling via `try/except` on bar loading with `SourceDegraded` event emission
- `RunResult.violations` feeds directly into `ConsistencyViolation` events and halt logic

### Negative Consequences

- Duplicated loop infrastructure (~150 lines) between backtest and pipeline
- The backtest creates positions directly instead of using `fill_entry_order` (I8 partial violation — P1.5)
- The pipeline does not call `validate.py` (step 2 of DESIGN §13 — P2.2)
- No staleness/DATA_HALT check in the pipeline

## References

- DESIGN.md §13: Daily run sequence
- ADR-0016: Degrade-don't-block failure model
- `src/app/pipeline.py`
- `src/app/backtest.py`
- Refinement backlog P1.5, P1.6, P2.2

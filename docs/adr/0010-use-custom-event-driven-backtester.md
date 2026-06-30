# ADR-0010: Use Custom Event-Driven Backtester

## Status

Superseded by ADR-0048 (Command Bus).

## Date

2026-06-10

## Context

Alpha-Quant's decision engine is path-dependent: positions held from prior days affect today's risk checks, available cash, and sector limits. This cannot be modeled with vectorized backtesting (which assumes independent decisions). A daily-step simulation is required.

DESIGN.md §14 specifies: "No vectorbt for portfolio simulation (path-dependent constraints); event-driven daily loop over domain/fills.py — a decade in seconds at this scale; vectorbt for single-signal research only."

## Decision Drivers

- Path-dependent portfolio simulation: positions, stops, cash, and sector limits persist across days
- Same fill model as paper: backtest must use exactly the same `domain/fills.py` (I8)
- Single-signal research can use vectorbt independently — not a replacement for the portfolio backtester
- Performance: 10 years × 9 symbols must complete in < 60 seconds
- Walk-forward compatibility: the backtester must support walk-forward analysis with parameter grids

## Considered Options

- **Option A: Custom event-driven backtester** — Daily loop, same Domain/Fill code as paper, path-dependent state
- **Option B: vectorbt** — Vectorized (array-based) for speed, but cannot model path-dependent portfolios correctly
- **Option C: Zipline** — Event-driven, mature, path-dependent; but heavy (requires Redis, large dependency tree), and the fill model cannot be customized without forking
- **Option D: Backtrader** — Event-driven, customizable; but Python 3.12 support is inconsistent, and the architecture is tightly coupled to its own data/model classes

## Decision Outcome

Chosen option: **Option A — Custom event-driven backtester**.

Rationale:
1. Path-dependent simulation is a hard requirement — vectorized tools silently produce wrong results for compounded portfolios
2. Same fill model guarantee (I8) is only achievable with a custom backtester — no existing framework can be patched to use `domain/fills.py` without invasive changes
3. 10 years × 9 symbols in < 60 seconds is achievable with the daily-step loop (3650 days × 9 symbols = 32,850 iterations — trivial for Python)
4. No framework coupling — the backtester is a thin loop over existing domain functions
5. vectorbt remains available for single-signal research (e.g., "does a 50/200 SMA crossover generate alpha on SPY?")

### Positive Consequences

- Backtest results are directly comparable to paper and replay — they share every line of domain code
- No framework upgrade risk (Zipline's maintenance has been intermittent)
- Walk-forward is a simple nested loop over the backtester
- The backtester code is ~100 lines: `for date in date_range: run_pipeline(date)`

### Negative Consequences

- Must implement from scratch (~100 lines for the loop, plus metrics computation)
- No built-in performance attribution, analytics, or reporting (must build these separately)
- Less feature-rich than Zipline for complex scenarios (but v1's scenarios are straightforward)

## References

- DESIGN.md §14 (Backtesting and evaluation), §16 (Invariant I8)
- RAD §5 (Container Architecture), §7 (Dynamic Views — daily run sequence)
- C4 Container diagram: `docs/architecture/views/container.png`
- ADR-0009 (Fill model)

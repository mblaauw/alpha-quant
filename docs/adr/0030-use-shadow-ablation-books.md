# ADR-0030: Use Shadow Ablation Books for Mechanism Evaluation

## Status

Accepted

## Date

2026-06-15

## Context

Alpha-Quant runs 8 decision mechanisms (M1–M8) that compose into a final entry decision. To evaluate whether each mechanism contributes positive value, we need controlled experiments: run the portfolio with and without each mechanism, then compare outcomes.

A production-grade approach runs multiple portfolios in parallel — one "full" and one or more "ablation" portfolios where a mechanism is disabled. These are "shadow books" because they run alongside (not instead of) the primary PAPER book.

The mechanisms that can be toggled for ablation are:
- **M5 (Insider)** — insider cluster boost and c-suite sell penalty
- **M6 (Crowding Veto)** — blocks entries for symbols with extreme social media mentions

Additional ablations (M3 technical without quality, M8 weighted differently) are future work.

## Decision Drivers

- **Parallel execution** — Shadow books must run in the same pipeline pass, using the same decisions but different fill/risk/entry logic
- **Isolation** — Each book has its own state (positions, equity curve) — they must not interfere
- **Comparison** — After sufficient runs, the system computes: full book performance vs each shadow book
- **Walk-forward by design** — Ablation is continuous, not a one-time experiment. Every run produces data for comparison

## Considered Options

- **Option A: ShadowBook class with toggles (current choice)** — `domain/ablation.py` defines `ShadowBook` that accepts `AblationConfig`. Each configured book runs as a separate portfolio with its own fill and portfolio logic. The factory creates three shadow books: `RULES_ONLY`, `NO_INSIDER`, `NO_CROWDING_VETO`
- **Option B: Run separate backtests** — Run the pipeline N times with different configurations. No shadow books needed
- **Option C: Post-hoc counterfactual** — Record all decisions and recompute outcomes without certain mechanisms

## Decision Outcome

Chosen option: **Option A — ShadowBook class with toggles**.

Rationale:
1. Shadow books run in the same pipeline pass — same bars, same clock, same universe. Fair comparison
2. `AblationConfig` is declarative: `disable_insider=True`, `disable_crowding_veto=True`
3. `compute_ablation_comparison()` aggregates results across books for comparison reports
4. Separate backtests (Option B) would use different clock ticks and market conditions — apples-to-oranges comparison
5. Post-hoc counterfactuals (Option C) ignore path-dependent effects (stops hit, fills rejected) — unrealistic

### Positive Consequences

- Walk-forward validation is built-in, not bolted on
- Shadow book results are persisted in `equity_curve` (differentiated by `book` column)
- `compute_ablation_comparison()` provides: return, CAGR, max drawdown, Sharpe ratio per book
- Adding a new shadow book is a one-line config change

### Negative Consequences

- 4x state writes per pipeline run (PAPER + 3 shadows) — more I/O
- Shadow fill results are computed but the shadow books do not interact with the primary book — no mechanism yet for auto-tuning based on ablation results
- Ablation results are meaningless until sufficient runs accumulate (months of paper trading)

## References

- DESIGN.md §9.3 (Shadow books)
- `domain/ablation.py`
- `config.toml` `[shadow]` section
- ADR-0022 (Paper Portfolio Engine)

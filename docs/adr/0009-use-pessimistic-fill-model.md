# ADR-0009: Use Custom Pessimistic Fill Model

## Status

Superseded by ADR-0011 (Book Fill Model).

## Date

2026-06-10

## Context

Alpha-Quant has no broker execution in v1 — fills are simulated internally. The fill model is the single most important component for simulation honesty: optimistic fills (fills always at the limit, no gap consideration, no slippage) produce paper results that mislead users and lead to wrong decisions about mechanism effectiveness.

DESIGN.md §9.2 specifies pessimistic semantics: gap-through-stop fills at the open, not the stop; gap-up entries cancel; slippage varies with market conditions.

## Decision Drivers

- Simulation honesty: paper results must be a realistic upper bound, not a fantasy
- One fill model across all execution realities (I8): backtest, replay, paper, shadows — identical semantics
- Gap-through-stop treatment: ATR stops that "never lose more than 1%" on paper but gap through in reality are how paper systems lie
- Deterministic and idempotent: re-running a day produces the same fills

## Considered Options

- **Option A: Custom pessimistic fill model** — Gap-through-stop fills at open, gap-up entries cancel, variable slippage from Alpaca quotes
- **Option B: Naive fill model** — Fill at limit, no gap handling, fixed slippage — simple but misleading
- **Option C: backtesting.py framework** — Has a built-in fill model, but designed for intraday bar testing; does not handle daily-bar gap semantics
- **Option D: Custom but optimistic** — Always fill at stop price, never cancel — gives better-looking results but violates the honesty principle

## Decision Outcome

Chosen option: **Option A — Custom pessimistic fill model**.

Rationale:
1. Gap-through-stop fills at open, not stop — this is the honest, realistic treatment. A stock that gaps below the stop on an earnings miss should not be modeled as filling at the stop price
2. Gap-up entries cancel (2% band) — prevents "perfect entry" bias in paper results
3. Variable slippage from live Alpaca quotes — during high volatility, slippage increases naturally
4. One model, five consumers (I8) — backtest, replay, paper, and 3 shadow books all use the same function
5. Idempotent by construction: `fill_id = hash(decision_id, fill_date)` — determinism is a non-negotiable property (I7)

### Positive Consequences

- Paper results are a realistic upper bound — the monthly report caveat is backed by honest modeling
- No "paper trading fairy" — decisions that work in simulation are more likely to work in live trading
- The monthly report's "paper-vs-live caveat" is meaningful rather than boilerplate
- Gap-through-stop treatment prevents the most common paper-trading fallacy

### Negative Consequences

- Paper results will look worse than naive fill models — this is correct but may be surprising to users who expect higher returns
- More complex implementation than a naive model (~200 lines vs ~50 lines)
- Requires Alpaca quotes for spread estimation (even in live paper mode)
- Need to explain the gap-through-stop semantics clearly in concept cards

## References

- DESIGN.md §9 (Internal paper-trading engine), §9.2 (Fill model semantics), §16 (Invariant I8)
- RAD §6.3 (Fill Model & Portfolio Components)
- C4 Component diagram (Fill Model): `docs/architecture/views/fillModelPortfolioComponents.png`

# ADR-0036: Neutral Facts in Alpha-Lake, Strategy Policy in Alpha-Quant

**Status:** Accepted

**Date:** 2026-06-25

## Context

Earlier versions of Alpha-Quant computed neutral market metrics locally: RSI, MACD, ATR, moving averages from raw bars; P/E, margins, debt ratios from raw financial statements; insider transaction aggregation and clustering; z-scores from raw mention counts. This duplicated work that Alpha-Lake now performs as its core service.

Local calculation created several problems:

1. **Logic duplication** — The same RSI formula or PE calculation could diverge between Alpha-Quant and Alpha-Lake.
2. **Data coupling** — Raw bars, statements, and transactions had to be fetched and stored locally, increasing complexity.
3. **Audit gaps** — Decision evidence referenced local calculations rather than server-side metric provenance.
4. **Maintenance burden** — Formula updates required changes in both systems.

## Decision

**Alpha-Lake computes and serves neutral observable facts. Alpha-Quant applies strategy-specific policy, ranking, risk, sizing, and execution rules.**

### Boundary

```
Alpha-Lake                        Alpha-Quant
─────────                        ──────────
RSI(14)              ───────►    technical_policy.evaluate(rsi=…)
ATR(14)              ───────►    sizing uses ATR for stop distance
P/E, margins         ───────►    fundamental_policy.evaluate(pe=…)
Insider summary      ───────►    insider_policy.evaluate(tx_summary=…)
Attention z-score    ───────►    attention_policy.evaluate(z_score=…)
Earnings events      ───────►    earnings_blackout_policy.evaluate(events=…)
Regime indicators    ───────►    regime_policy.detect(ema50=…, breadth=…)
```

### Rules

1. **No Alpha-Quant metric recalculates a neutral Alpha-Lake metric.** If Alpha-Lake provides `momentum.rsi_14`, Alpha-Quant uses it directly. If Alpha-Lake does not yet serve a needed metric, the gap must be filled by an Alpha-Lake endpoint — not by local calculation.

2. **No Alpha-Lake metric is interpreted as a trade recommendation.** Alpha-Lake states `tone: "green"` or `state: "high_return_on_capital"` as neutral factual observations. Alpha-Quant policy independently decides whether that observation supports an entry.

3. **Alpha-Quant policy may classify a fact for its strategy.** Policy may decide that a P/E of 15 is "attractive" or "expensive" depending on the strategy context. But classification labels must be clearly distinguished from Alpha-Lake's neutral `tone`.

4. **Decision evidence must reference the source observation.** Every scored factor must record which Alpha-Lake `metric_id`, `value`, `state`, and `tone` informed the decision.

### Implementation

Policy modules in `src/alpha_quant/domain/policy/` apply thresholds and rules to `DecisionContext` values. They have no access to raw bars, statements, or transaction records. The `DecisionContext` is assembled from the Alpha-Lake decision-panel batch response.

## Consequences

### Positive

- Single source of truth for all neutral metric definitions.
- Alpha-Quant policy is simpler — only decision logic, no calculation code.
- Metric updates affect Alpha-Quant immediately (via the REST API contract).
- Evidence audit trail references Alpha-Lake metric IDs and provenance.

### Negative

- Alpha-Quant cannot compute a needed metric if Alpha-Lake does not serve it (requires coordinated endpoint addition).
- Policy tests depend on Alpha-Lake metric shapes being stable (enforced by contract versioning).
- Alpha-Quant loses the ability to "tweak" metric calculation independently of Alpha-Lake — intentional, but requires discipline.

## References

- ADR-0035 (Alpha-Lake REST Is the Sole Facts Plane)
- ADR-0033 (PIT reads via Clock-driven `as_of`)

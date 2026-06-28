# ADR-0056: Real Risk Engine Replaces Placeholder Calculations

## Status

Accepted

## Date

2026-06-28

## Context

The Risk Desk GUI was implemented against a contract-complete placeholder
response from `GET /v1/console/risk` (see ADR-0055). The placeholder used
hardcoded values for VaR, correlation, volatility, beta, and scenario P&L,
and marked itself with `var.method_params.placeholder = true`.

The real risk engine is now implemented behind the same API contract. It
replaces every placeholder value with a methodology-backed calculation while
preserving the field names and types the GUI expects.

## Decision

`/v1/console/risk` is now backed by the `RiskEngine` class in
`src/alpha_quant/application/risk/`. The engine is organized as 10 workstreams
(WS1–WS10) implementing:

| Area | Module | Methodology |
|------|--------|-------------|
| Inputs | `inputs.py` | Load positions, sectors from `core.security_reference`, compute equity |
| VaR & ES | `var.py` | Parametric (variance-covariance, EWMA λ=0.94), historical (500-day sorted returns), Monte Carlo (10k paths, Cholesky, LCG deterministic seed) |
| Component VaR | `component.py` | Euler allocation: marginal VaR → component VaR → flag when CVaR/w > 1.5× weight |
| Scenarios | `scenarios.py` | Historical replay (2008 −34%, COVID −21%, 2018 Q4 −17%) + hypothetical shocks (Tech −15%, VIX +10, Rates +100bp), ranked by severity |
| Concentration | `concentration.py` | HHI, effective N = 1/HHI, top-3 concentration, average pairwise correlation, diversification ratio, sector caps at 70% |
| Factor exposures | `factors.py` | Market beta via OLS, momentum/value/size/volatility/quality tilts z-scored and normalized to [−1, +1] |
| Liquidity | `liquidity.py` | Days-to-liquidate at 20% of ADV, $1B ADV fallback | 
| Limits | `limits.py` | Policy threshold checks: gross 90%, VaR 4%, drawdown 10%, sector 70%, single-name 25%; breach→crit, ≥85%→warn |
| Posture | `posture.py` | halt > elevated > ready state machine from events |
| Orchestration | `__init__.py` | `RiskEngine.run()` calls all modules, formats the response dict |

## Key Design Properties

- **Deterministic**: Monte Carlo VaR uses a fixed LCG seed (42) and the
  covariance computation is purely a function of the return series.
- **Explainable**: Every headline number can be traced to a specific method
  and input data.
- **Contract-stable**: The response dict has the same keys as the placeholder.
  The GUI did not need any changes.
- **Graceful degradation**: Missing positions → zero VaR with an info event.
  Missing ADV → $1B fallback. Single position → correlation = 0, style tilts = 0.

## Consequences

Positive:
- Risk dashboard numbers are now methodology-backed, not hardcoded.
- The `placeholder: True` marker is removed.
- Event text no longer references "issue #612" or "placeholder".
- The same `RiskEngine` can be used by the order-ticket guardrails for
  consistent limit checking.

Negative:
- Return data is currently synthetic (generated from position prices) because
  the Alpha-Lake `daily_return` readout is not yet available. Real return
  data will improve VaR accuracy when wired.
- Style factor tilts use placeholder metrics until the Lake provides
  momentum/value/quality readouts.
- The covariance matrix uses EWMA on synthetic returns; real return series
  from Lake will change VaR magnitudes (not structure).

## Comparison to ADR-0055

| Aspect | Placeholder (ADR-0055) | Real Engine (this ADR) |
|--------|----------------------|----------------------|
| VaR 99% | Fixed 3.6% | Computed from covariance × z-score |
| Expected Shortfall | 3.1% (renamed percentile) | Tail average of worst 2.5% returns |
| Component VaR | Hardcoded index-based vol/beta | Euler allocation from covariance |
| Scenarios | Fixed % of gross × equity | Same structure, values from current weights |
| Correlation | Fixed 0.58 | Computed pairwise from returns |
| Factor tilts | Fixed ±0.42/0.55/0.31/0.38/0.22 | Z-scored from metrics, normalized to ±1 |
| Limits | Same structure | Same structure, thresholds aligned |
| Events | Placeholder text about issue #612 | Real breach/caution events |
| `placeholder` flag | `true` | Removed |

# Parameter Sensitivity Analysis (Walk-Forward)

**Status:** Pending (requires ≥3 months paper trading data)

## Parameters

| Parameter | Default | Grid Values |
|-----------|---------|-------------|
| `stop_atr_mult` | 2.0 | [1.5, 2.0, 2.5] |
| `risk_per_trade_pct` | 0.01 | [0.005, 0.01, 0.02] |
| `max_positions` | 8 | [6, 8, 10] |

Total: 27 combinations.

## Walk-Forward Setup

- Training window: 3 years
- Test window: 1 year
- Roll forward: every 6 months
- Metric: Sharpe ratio

## Outputs

- Surface plots for each parameter pair
- Optimal parameter region (contours)
- Stability measure: CV of Sharpe across windows

## Results

*To be filled after ≥3 months of paper trading data is available.*

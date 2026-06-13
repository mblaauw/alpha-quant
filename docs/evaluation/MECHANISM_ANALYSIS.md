# Mechanism Ablation Analysis

**Status:** Pending (requires ≥3 months paper trading data)

## Method

For each mechanism (M1–M8), compare:
- PAPER portfolio (all mechanisms enabled)
- Ablation portfolio (mechanism disabled, everything else identical)

Metrics compared:
- Sharpe ratio (annualized)
- CAGR
- Max drawdown
- Win rate

## Bootstrap Test

The Sharpe difference is bootstrap-tested with 1000× resampling of daily returns.
If p > 0.10, the mechanism is flagged for potential removal.

## Cost Analysis

- Turnover by mechanism
- Slippage impact per mechanism
- Net benefit after costs

## Results

*To be filled after ≥3 months of paper trading data is available.*

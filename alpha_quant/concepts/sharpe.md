---
id: sharpe
title: "Sharpe Ratio Explained"
difficulty: intermediate
---

The Sharpe ratio measures the excess return per unit of risk. It tells you whether a strategy's returns are compensation for smart decisions or simply for taking on more risk.

The formula is: (portfolio return − risk-free rate) / standard deviation of returns. A Sharpe ratio above 1 is considered good, above 2 very good, and above 3 excellent. In Alpha Quant, the backtester computes Sharpe using daily returns annualized by the square root of 252 (trading days per year).

The Sortino ratio is a variant that penalizes only downside volatility — it divides excess return by the standard deviation of negative returns only. Both are computed automatically by the backtester and reported in every BacktestMetrics result.

**Key takeaway:** Sharpe ratio tells you if returns justify the risk taken. Higher is better. Sortino is the downside-focused version.

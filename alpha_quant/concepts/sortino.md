---
id: sortino
title: "Sortino Ratio Explained"
difficulty: intermediate
---

The Sortino ratio is a variation of the Sharpe ratio that only penalizes downside volatility. While the Sharpe ratio treats all volatility as bad (up moves and down moves alike), the Sortino ratio recognizes that investors prefer upside volatility and only want to minimize downside risk.

The formula is: (portfolio return − risk-free rate) / downside deviation, where downside deviation is the standard deviation of only the negative returns. This makes the Sortino ratio a better measure for strategies that generate many small gains with occasional losses.

In Alpha Quant, both Sharpe and Sortino are computed by the backtester's _compute_metrics function. Comparing the two numbers reveals the nature of the strategy's risk: a strategy with similar Sharpe and Sortino has symmetric risk (gains and losses are equally volatile), while a much higher Sortino indicates the strategy protects the downside well.

**Key takeaway:** Sortino focuses on downside risk only. A Sortino much higher than Sharpe means the strategy protects capital during drawdowns.

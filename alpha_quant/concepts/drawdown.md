---
id: drawdown
title: "What is Drawdown?"
difficulty: beginner
---

Drawdown measures the decline in portfolio value from its peak to its trough. If your portfolio peaks at $100,000 and then falls to $85,000, your drawdown is 15%. It is the most intuitive measure of downside risk.

Alpha Quant uses drawdown in two ways. First, it triggers a ladder of risk-reduction actions: if drawdown exceeds 10%, the system cuts position sizes by 50%; if it exceeds 15%, all new positions are halted until the portfolio recovers. Second, drawdown is used in backtest metrics alongside Sharpe and Sortino ratios to give a complete picture of risk-adjusted performance.

Drawdown is distinct from loss — a 15% drawdown means the portfolio is 15% below its all-time high, even if the day's return was positive. Recovery from a drawdown requires the portfolio to gain more than the drawdown percentage (a 20% drawdown needs a 25% gain to break even).

**Key takeaway:** Drawdown measures peak-to-trough decline. The system cuts risk automatically as drawdown deepens.

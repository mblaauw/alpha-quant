---
id: backtesting
title: "Backtesting Strategies"
difficulty: intermediate
---

Backtesting simulates a trading strategy on historical data to evaluate its performance before risking real capital. Alpha Quant's backtester runs a daily loop over a date range, processing the same signals and rules as the live pipeline.

The backtester loads bars for all symbols, derives indicator states incrementally (one day at a time), evaluates risk exits, scores candidates, ranks them, sizes positions, and tracks portfolio equity daily. It uses the same fill model (fill_entry_order, fill_stop_loss) as the paper portfolio and live system — ensuring results are comparable across all execution realties.

Performance metrics include total return, CAGR, maximum drawdown, Sharpe ratio, Sortino ratio, number of trades, win rate, and average hold days. The backtester stores results as BacktestResult with a full step-by-step equity curve.

**Key takeaway:** The backtester uses the same code as the live system. Backtest, paper, and live fills are identical by design.

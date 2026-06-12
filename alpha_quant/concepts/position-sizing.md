---
id: position-sizing
title: "Position Sizing Fundamentals"
difficulty: intermediate
---

Position sizing determines how many shares to buy for each trade. It is the most under-appreciated element of trading — even a high-win-rate strategy fails with bad sizing.

Alpha Quant sizes every position using the Kelly-inspired risk budget approach. The system calculates: risk_notional = equity × risk_per_trade_pct × regime_mult × dd_mult. This is converted to a dollar amount by dividing by (stop_atr_mult × ATR). The result is capped by max_position_pct of equity to prevent concentration in any single name.

The risk-per-trade is typically 1% of equity. In a RISK_ON regime with no drawdown, a $100,000 account risks $1,000 per trade. In CAUTION, this drops to $500. If drawdown exceeds 10%, the dd_mult drops to 0.5, halving sizes further.

**Key takeaway:** Position size adapts to volatility (ATR), regime (multiplier), and drawdown. Every trade risks the same fixed percentage of equity.

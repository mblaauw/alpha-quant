---
id: atr
title: "What is ATR (Average True Range)?"
difficulty: beginner
---

Average True Range (ATR) measures how much a security's price typically moves over a given period. Developed by J. Welles Wilder, it is a volatility indicator, not a directional one — it tells you how much the price moves, not which way.

ATR is calculated as the maximum of the current high minus the current low, the absolute value of the current high minus the previous close, and the absolute value of the current low minus the previous close. The true range is then averaged over a lookback window (typically 14 periods).

In Alpha Quant, ATR feeds directly into position sizing: a stock with high ATR gets a smaller position to keep risk per trade consistent. It also drives stop-loss placement — stops are set at ATR multiples below the entry price (typically 2× ATR). When ATR expands, volatility is rising and the system adapts positions accordingly.

**Key takeaway:** ATR measures market volatility and determines how much risk each position carries. Higher ATR = smaller positions.

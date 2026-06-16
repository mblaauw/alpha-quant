---
id: moving-averages
title: "Moving Averages (SMA and EMA)"
difficulty: beginner
---

A moving average smooths price data by averaging it over a fixed window. The Simple Moving Average (SMA) gives equal weight to each price point, while the Exponential Moving Average (EMA) gives more weight to recent data.

Alpha Quant uses EMAs exclusively — the 50-day and 200-day EMAs on SPY for regime detection. When SPY's price is above both EMAs and the 50-day EMA is above the 200-day EMA (a "golden cross" configuration), the regime is RISK_ON. If price falls below either EMA, the system downgrades to CAUTION or RISK_OFF.

EMAs are computed incrementally: the update_indicator_state function processes one bar at a time in O(1) time, making it efficient for both backtesting (thousands of bars) and daily pipeline runs (single bar update).

**Key takeaway:** EMAs define the trend. 50-day vs 200-day EMA crossovers determine the market regime in Alpha Quant.

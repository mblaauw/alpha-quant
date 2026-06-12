---
id: rsi
title: "What is RSI (Relative Strength Index)?"
difficulty: beginner
---

The Relative Strength Index (RSI) is a momentum oscillator that measures the speed and magnitude of recent price changes. It ranges from 0 to 100 and is used to identify overbought or oversold conditions.

RSI is calculated by comparing the average of up-day closes to the average of down-day closes over a lookback period (typically 14 days). Readings above 70 are considered overbought, below 30 oversold.

Alpha Quant uses RSI as one component of the technical score. A stock with RSI between 45 and 70 scores best — it has upward momentum without being dangerously over-extended. If RSI is missing or NaN, the candidate is skipped entirely (no score = no trade).

**Key takeaway:** RSI measures momentum. The sweet spot for entry is RSI between 45 and 70 — strong but not overheated.

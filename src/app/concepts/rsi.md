---
id: rsi
title: "What is RSI (Relative Strength Index)?"
difficulty: beginner
---

The Relative Strength Index (RSI) is a momentum oscillator that measures the speed and magnitude of recent price changes. It ranges from 0 to 100 and is used to identify overbought or oversold conditions.

RSI is calculated by comparing the average of up-day closes to the average of down-day closes over a lookback period (typically 14 days). Readings above 70 are considered overbought, below 30 oversold.

Alpha Quant uses RSI as one component of the technical score. The RSI sub-score follows a Gaussian centered at 52 ± 22 — scores near 52 score highest (1.0), dropping off symmetrically. If RSI is missing or NaN, the sub-score returns 0.3 (not a full disqualification — other factors still contribute).

**Key takeaway:** RSI measures momentum. The sweet spot is centered at 52, falling off as the Gaussian spreads to extreme levels.

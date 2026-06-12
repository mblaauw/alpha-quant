---
id: regime
title: "Understanding Market Regimes"
difficulty: intermediate
---

A market regime describes the overall state of the market — whether it is trending up, down, or moving sideways with uncertainty. Alpha Quant classifies regimes as RISK_ON, CAUTION, or RISK_OFF using a combination of technical indicators on SPY.

The regime detection looks at three key signals: the price relative to its 50-day and 200-day exponential moving averages, the VIX volatility index, and market breadth (how many stocks are participating in the move). When price is above both EMAs, VIX is low, and breadth is strong, the system declares RISK_ON and deploys capital fully. If any signal weakens, it downgrades to CAUTION (50% exposure) or RISK_OFF (no new positions).

Regime changes are cached and tracked — when a transition occurs, an event is emitted and all subsequent decisions use the new multiplier.

**Key takeaway:** Regime detection is the master switch. In RISK_ON, the system is aggressive. In RISK_OFF, capital preservation is the priority.

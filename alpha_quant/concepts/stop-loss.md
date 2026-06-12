---
id: stop-loss
title: "How Stop-Loss Orders Work"
difficulty: beginner
---

A stop-loss order is a pre-defined instruction to exit a position when its price reaches a specified level. Its purpose is to limit losses by automatically closing losing trades before they get worse.

In Alpha Quant, every position has a stop-loss set at an ATR multiple below the entry price (typically 2× ATR below). This means the stop adapts to market conditions — in volatile markets it is wider, in calm markets tighter. As the trade moves in your favor, trailing stops lock in profits by raising the stop price.

The system also uses time stops: if a position has been held beyond a configurable period (default 30 days) without hitting targets, it is automatically closed. This prevents capital being tied up in stagnant trades.

**Key takeaway:** Stop-losses are the foundation of risk control. Every position in Alpha Quant has one at an adaptive, volatility-aware distance.

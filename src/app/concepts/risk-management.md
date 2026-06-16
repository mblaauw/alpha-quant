---
id: risk-management
title: "Risk Management in Trading"
difficulty: intermediate
---

Risk management is the set of rules that prevent single losses from crippling a portfolio. In Alpha Quant, it operates at three levels: per-position stops, portfolio-level drawdown limits, and daily loss limits.

Per-position: every entry gets a stop-loss at 2× ATR below the entry price. As the trade moves in favor, trailing stops lock in profits. At +2× ATR profit (+1R), the trailing stop activates. At +4× ATR profit (+2R), a partial take-profit closes half the position. Trades held over 30 days are closed by time stop.

Portfolio-level: the drawdown ladder cuts position sizes progressively — 10% drawdown reduces sizing by 50%, 15%+ drawdown halts all new positions. The daily loss limit halts trading for the day if P&L drops below −3% of equity.

When any risk action triggers, an event is emitted (StopAdjusted, PartialTaken, TimeStopTriggered, DrawdownLadderTripped) so the system has a complete audit trail.

**Key takeaway:** Risk management works at three levels: per-position stops, portfolio drawdown ladder, and daily loss limit.

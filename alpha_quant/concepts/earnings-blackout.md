---
id: earnings-blackout
title: "Earnings Blackout Windows"
difficulty: intermediate
---

The earnings blackout rule prevents entering new positions in a stock during the three trading days before its earnings report. This avoids the risk of adverse price moves driven by earnings surprises rather than the system's normal signals.

When a stock has an upcoming earnings date in its earnings calendar, the system computes a blackout window: three trading days before the report date. The check is case-insensitive on the symbol. If no earnings date exists for the symbol, the check passes.

If the earnings calendar is stale (data source degraded), the system extends the blackout window by one day as a conservative fallback. This is defined in the DegradationStatus framework.

**Key takeaway:** No entries in the 3 days before earnings. This avoids event-driven volatility that technical analysis cannot predict.

---
id: insider-signal
title: "Insider Trading Signals"
difficulty: advanced
---

Insider trading signals are based on the academic finding by Cohen, Malloy, and Pomorski (2012) that clusters of open-market insider purchases predict positive future returns. When multiple corporate insiders buy stock in the same company within a short window, it signals conviction.

The M5 Insider Signal module detects clusters of two or more officers or directors who collectively purchased at least $200,000 worth of stock within the past 30 days. Each insider's title is checked — if the title contains "officer", "director", "CEO", "CFO", or related keywords, they count toward the threshold.

When a valid cluster is detected, the insider score is set to 0.15 and contributed at 15% weight to the composite ranking. If no cluster exists, the score is 0.0 and the ranking uses the standard 70/30 technical/momentum split.

**Key takeaway:** Insider buying clusters (≥2 executives, ≥$200k in 30 days) trigger a 0.15 score boost in the ranking system.

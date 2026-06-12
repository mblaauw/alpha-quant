---
id: crowding
title: "Crowding and Sentiment"
difficulty: intermediate
---

Crowding measures how much attention a stock is getting from retail investors on social media. Extreme attention is a contrarian signal — when a stock's mention count spikes far above its normal level, it often means the crowd has piled in and a reversal is near.

The M6 Crowding Veto uses a z-score approach. The system maintains a 30-day baseline of Reddit mention counts (mean and standard deviation). Each day, the current mention count is converted to a z-score: (daily − mean_30d) / std_30d.

When the z-score exceeds 3.0, a 14-day (≈10 trading day) entry block is placed on that symbol. The block is stored as blocked_until date and checked before any new entry. If the Reddit data source is degraded, the block is lifted and the M3 composite threshold is increased by 20%.

**Key takeaway:** Reddit mentions >3 standard deviations above normal trigger a 10-day trading ban on new entries.

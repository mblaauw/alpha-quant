---
id: diversification
title: "Portfolio Diversification"
difficulty: beginner
---

Diversification is the practice of spreading investments across different assets to reduce risk. The core idea is that not all assets move in the same direction at the same time — when one position falls, others may hold steady or rise.

Alpha Quant implements diversification through explicit caps. The max_position_pct config (default 15%) prevents any single position from consuming too much capital. If the position sizing algorithm calculates a position above this cap, it is reduced to the cap level. The max_gross_exposure (default 80%) limits total market exposure, keeping at least 20% of equity in cash.

The ranking system also promotes diversification through ADV-based tiebreaking — when two candidates have equal scores, the one with higher average daily volume wins, favoring more liquid and typically larger-cap names.

**Key takeaway:** Diversification is enforced through position size caps and maximum portfolio exposure limits. No single stock dominates.

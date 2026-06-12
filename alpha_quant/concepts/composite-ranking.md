---
id: composite-ranking
title: "Composite Ranking System"
difficulty: advanced
---

The M8 Composite Ranking system is the final gate before position entry. It takes all scored candidates, filters by gate results, computes a composite score, sorts by score, and returns the top N positions up to the available slots.

The composite score uses a weighted formula that changes based on available signals. With only technical and momentum (the baseline), the weights are 70% technical and 30% momentum. When the M5 insider signal is available, the formula shifts to 60% technical, 25% momentum, and 15% insider. This is a deliberate design: additional signals reduce the dominance of any single factor.

Only candidates with composite_score > 0.5 pass the threshold. Ties are broken by average daily volume (ADV) — higher liquidity wins. Blocked candidates (those with gate failures or block_reason set) are excluded before scoring.

**Key takeaway:** The ranking system blends technical, momentum, and (when available) insider signals. Only scores above 0.5 are considered.

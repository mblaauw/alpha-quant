---
id: ablation
title: "Ablation Analysis"
difficulty: advanced
---

Ablation analysis measures the contribution of each mechanism to overall system performance by running the system with that mechanism disabled. It answers the question: "does the insider signal actually improve results, or would we be better off without it?"

Alpha Quant supports four books: PAPER (all mechanisms active), RULES_ONLY (permanent internal baseline with no alt-data signals), NO_INSIDER (M5 disabled, ranking uses 70/30 technical/momentum), and NO_CROWDING_VETO (M6 disabled, no Reddit mention blocks). Each book runs during every pipeline execution and stores its own equity curve.

The `compute_ablation_comparison()` function computes the annualized Sharpe ratio for each book and compares them. If an ablation book's Sharpe ratio exceeds PAPER's, the mechanism is flagged for manual review. The comparison requires at least 10 daily returns for statistical significance.

**Key takeaway:** Ablation analysis measures the real contribution of each mechanism. Underperformers are flagged for review.

---
id: ablation
title: "Ablation Analysis"
difficulty: advanced
---

Ablation analysis measures the contribution of each mechanism to overall system performance by running the system with that mechanism disabled. It answers the question: "does the insider signal actually improve results, or would we be better off without it?"

Alpha Quant supports three books: PAPER (all mechanisms active), NO_INSIDER (M5 disabled, ranking uses 70/30 technical/momentum), and NO_CROWDING_VETO (M6 disabled, no Reddit mention blocks). Each book runs during every pipeline execution and stores its own equity curve.

The AblationComparator computes the annualized Sharpe ratio for each book and compares them. If an ablation book outperforms PAPER for two consecutive quarters, the corresponding mechanism is flagged for manual review. The comparison uses at least 10 daily returns for statistical significance.

**Key takeaway:** Ablation analysis measures the real contribution of each mechanism. Underperformers are flagged for review.

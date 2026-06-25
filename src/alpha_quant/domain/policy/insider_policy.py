from __future__ import annotations

from alpha_quant.domain.decision_context import DecisionContext


def evaluate(context: DecisionContext) -> float:
    """Insider signal score from Alpha-Lake insider facts.

    Returns a score in [0, 1] where higher values indicate stronger
    insider conviction signals. Uses transaction direction counts
    rather than re-aggregating raw values.
    """
    txs = context.insider_transactions
    if not txs:
        return 0.0

    buys = sum(1 for t in txs if t.transaction_type.lower().startswith(("buy", "p")))
    sells = sum(1 for t in txs if t.transaction_type.lower().startswith(("sell", "s")))

    total = buys + sells
    if total == 0:
        return 0.0

    net_ratio = (buys - sells) / total
    if net_ratio <= 0:
        return 0.0

    return min(1.0, net_ratio * (total / 5))

from __future__ import annotations

from statistics import mean, stdev

from alpha_quant.domain.decision_context import DecisionContext


def evaluate(context: DecisionContext) -> bool:
    """Attention/crowding veto gate.

    Returns True if the symbol is NOT crowded (no veto).
    Returns False (veto) if attention is abnormally high.

    Uses Alpha-Lake mention counts to detect crowding events.
    No raw sentiment calculation is performed locally.
    """
    mentions = context.attention_mentions
    if len(mentions) < 2:
        return True

    values = [m.count for m in mentions]
    latest = values[-1]
    avg = mean(values)
    std = stdev(values) if len(values) > 1 else 0.0

    if std <= 0:
        return True

    z_score = (latest - avg) / std
    return z_score <= 3.0

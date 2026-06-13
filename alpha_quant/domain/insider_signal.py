from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel, ConfigDict

from alpha_quant.domain.models import InsiderTransaction

_OFFICER_KEYWORDS = {"ceo", "cfo", "coo", "president", "officer", "vp", "evp", "svp"}


class InsiderVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)
    score: float
    reason: str | None = None


def evaluate(
    symbol: str,
    transactions: list[InsiderTransaction],
    as_of_date: date,
    lookback: int = 30,
) -> InsiderVerdict:
    cutoff = as_of_date - timedelta(days=lookback)

    buy_txns = [
        t
        for t in transactions
        if t.symbol.upper() == symbol.upper()
        and t.transaction_date is not None
        and t.transaction_date >= cutoff
        and t.transaction_date <= as_of_date
        and t.transaction_type.lower() == "buy"
        and t.price is not None
        and t.price > 0
        and t.shares_traded > 0
    ]

    if not buy_txns:
        return InsiderVerdict(score=0.0, reason="no insider buys in window")

    officers: set[str] = set()
    directors: set[str] = set()
    total_value = 0.0

    for t in buy_txns:
        assert t.price is not None
        total_value += t.shares_traded * t.price
        if t.title:
            title_lower = t.title.lower()
            if "director" in title_lower:
                directors.add(t.owner)
            if _is_officer_role(title_lower):
                officers.add(t.owner)

    combined = officers | directors
    cluster_size = len(combined)

    if cluster_size >= 2 and total_value >= 200_000:
        return InsiderVerdict(
            score=0.15,
            reason=(
                f"cluster: {len(officers)} officers, {len(directors)} directors,"
                f" ${total_value:,.0f} in {lookback}d"
            ),
        )

    return InsiderVerdict(
        score=0.0,
        reason=(f"no cluster: {cluster_size} insiders, ${total_value:,.0f} in {lookback}d"),
    )


def _is_officer_role(title_lower: str) -> bool:
    if "officer" in title_lower:
        return True
    return any(kw in title_lower for kw in _OFFICER_KEYWORDS)

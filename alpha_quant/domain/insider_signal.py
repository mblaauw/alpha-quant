"""Insider transaction clustering and signal generation."""

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
    market_cap: float | None = None,
    min_cluster_value: float = 200_000.0,
    min_cluster_size: int = 2,
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

    sell_txns = [
        t
        for t in transactions
        if t.symbol.upper() == symbol.upper()
        and t.transaction_date is not None
        and t.transaction_date >= cutoff
        and t.transaction_date <= as_of_date
        and t.transaction_type.lower() == "sell"
    ]

    if not buy_txns:
        sell_penalty = _sell_penalty(sell_txns)
        if sell_penalty > 0:
            return InsiderVerdict(
                score=-sell_penalty, reason=f"c-suite selling ({len(sell_txns)} sells)"
            )  # noqa: E501
        return InsiderVerdict(score=0.0, reason="no insider activity in window")

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

    effective_min = (
        min(max(market_cap * 0.0001, min_cluster_value), 10_000_000.0)
        if market_cap and market_cap > 0
        else min_cluster_value
    )  # noqa: E501
    if cluster_size < min_cluster_size or total_value < effective_min:
        sell_penalty = _sell_penalty(sell_txns)
        score = -sell_penalty if sell_penalty > 0 else 0.0
        return InsiderVerdict(
            score=score,
            reason=(
                f"below threshold: {cluster_size} insiders, ${total_value:,.0f} in {lookback}d"
            ),  # noqa: E501
        )

    if market_cap and market_cap > 0:
        value_ratio = total_value / market_cap
        value_score = min(1.0, value_ratio * 500)
    else:
        value_score = min(1.0, total_value / 5_000_000)

    size_bonus = min(0.5, cluster_size * 0.05)
    officer_bonus = min(0.3, len(officers) * 0.08)
    sell_penalty = _sell_penalty(sell_txns)

    score = round(
        max(
            0.0, min(0.5, value_score * 0.3 + size_bonus * 0.1 + officer_bonus * 0.1 - sell_penalty)
        ),
        4,
    )  # noqa: E501

    return InsiderVerdict(
        score=score,
        reason=(
            f"cluster: {len(officers)} officers, {len(directors)} directors,"
            f" ${total_value:,.0f} ({value_score:.2f}) in {lookback}d"
        ),
    )


def _sell_penalty(sell_txns: list[InsiderTransaction]) -> float:
    c_suite_sells = sum(1 for t in sell_txns if t.title and _is_officer_role(t.title.lower()))
    if c_suite_sells >= 3:
        return min(0.3, c_suite_sells * 0.05)
    return 0.0


def _is_officer_role(title_lower: str) -> bool:
    if "officer" in title_lower:
        return True
    return any(kw in title_lower for kw in _OFFICER_KEYWORDS)

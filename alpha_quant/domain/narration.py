"""Narration/description generation for trades and decisions."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from alpha_quant.domain.events import (
    BaseDomainEvent,
    CandidateBlocked,
    CandidatePromoted,
    CandidateScored,
    SourceDegraded,
)
from alpha_quant.domain.models import Position


class PositionNarration(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    shares: float
    entry_price: float | None
    current_price: float | None
    avg_cost: float
    unrealized_pl: float | None
    stop_price: float | None
    risk_pct: float | None


class NarrationContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    date: date
    regime: str
    data_health: dict[str, bool]
    candidates_scored: int
    candidates_blocked: int
    candidates_promoted: int
    positions: list[PositionNarration]
    equity: float
    cash: float
    concept_of_day: str | None


def build(
    run_date: date,
    events: list[BaseDomainEvent],
    positions: list[Position],
    equity: float,
    cash: float,
    regime: str,
    concept_of_day: str | None = None,
) -> NarrationContext:
    scored = sum(1 for e in events if isinstance(e, CandidateScored))
    blocked = sum(1 for e in events if isinstance(e, CandidateBlocked))
    promoted = sum(1 for e in events if isinstance(e, CandidatePromoted))

    degraded_sources = {e.source_name for e in events if isinstance(e, SourceDegraded)}
    data_health: dict[str, bool] = {}
    for src in ("eodhd", "alpaca", "openinsider", "reddit", "sec"):
        data_health[src] = src not in degraded_sources

    pos_narrations: list[PositionNarration] = []
    for p in positions:
        if p.quantity <= 0:
            continue
        risk_pct: float | None = None
        if (
            p.stop_price is not None
            and p.current_price is not None
            and p.avg_cost is not None
            and equity > 0
        ):
            risk_pct = round((p.current_price - p.stop_price) / p.avg_cost * 100, 2)

        pos_narrations.append(
            PositionNarration(
                symbol=p.symbol,
                shares=p.quantity,
                entry_price=p.entry_price,
                current_price=p.current_price,
                avg_cost=p.avg_cost,
                unrealized_pl=p.unrealized_pl,
                stop_price=p.stop_price,
                risk_pct=risk_pct,
            )
        )

    return NarrationContext(
        date=run_date,
        regime=regime,
        data_health=data_health,
        candidates_scored=scored,
        candidates_blocked=blocked,
        candidates_promoted=promoted,
        positions=pos_narrations,
        equity=round(equity, 2),
        cash=round(cash, 2),
        concept_of_day=concept_of_day,
    )

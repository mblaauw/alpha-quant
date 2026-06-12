from __future__ import annotations

from datetime import date

from alpha_quant.domain.models import CorporateAction


def compute_adjustment_factor(
    corp_actions: list[CorporateAction],
    as_of_date: date,
) -> float:
    sorted_actions = sorted(
        [ca for ca in corp_actions if ca.action_type == "split"],
        key=lambda x: x.effective_date,
    )
    factor = 1.0
    for ca in sorted_actions:
        if ca.effective_date > as_of_date and ca.ratio is not None and ca.ratio != 0.0:
            factor *= ca.ratio
    return factor


def adjust_price(
    raw_price: float,
    corp_actions: list[CorporateAction],
    as_of_date: date,
) -> float:
    factor = compute_adjustment_factor(corp_actions, as_of_date)
    if factor == 1.0:
        return raw_price
    return raw_price / factor


def is_state_stale(state_date: date, corp_actions: list[CorporateAction]) -> bool:
    return any(ca.effective_date > state_date for ca in corp_actions)

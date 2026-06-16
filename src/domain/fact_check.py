"""Fact-checking utilities for LLM-generated content."""

from __future__ import annotations

import re

from domain.narration import NarrationContext

_NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?")

_TEMPLATE = (
    "## {date} — Daily Summary\n\n"
    "Regime: {regime}\n"
    "Equity: ${equity:,.2f}\n"
    "Cash: ${cash:,.2f}\n"
    "Candidates scored: {scored} | blocked: {blocked} | promoted: {promoted}\n"
    "Open positions: {position_count}\n"
    "Concept: {concept}\n"
)


def _build_allowlist(ctx: NarrationContext) -> set[str]:
    allow: set[str] = set()

    def add(val: float | int) -> None:
        s = str(val)
        allow.add(s)
        if "." in s:
            allow.add(s.rstrip("0").rstrip(".") if "." in s else s)
            allow.add(f"{val:.2f}" if isinstance(val, float) else str(val))

    for v in (
        ctx.candidates_scored,
        ctx.candidates_blocked,
        ctx.candidates_promoted,
        ctx.equity,
        ctx.cash,
        int(ctx.equity),
        int(ctx.cash),
    ):
        add(v)

    for p in ctx.positions:
        add(p.shares)
        add(int(p.shares))
        for field in (
            p.entry_price,
            p.current_price,
            p.avg_cost,
            p.unrealized_pl,
            p.stop_price,
            p.risk_pct,
        ):
            if field is not None:
                add(field)
                add(int(field))

    return allow


def verify(llm_output: str, context: NarrationContext) -> bool:
    allowlist = _build_allowlist(context)
    numbers = _NUMBER_RE.findall(llm_output)
    return all(num in allowlist for num in numbers)


def render_template(context: NarrationContext) -> str:
    return _TEMPLATE.format(
        date=context.date.isoformat(),
        regime=context.regime,
        equity=context.equity,
        cash=context.cash,
        scored=context.candidates_scored,
        blocked=context.candidates_blocked,
        promoted=context.candidates_promoted,
        position_count=len(context.positions),
        concept=context.concept_of_day or "none",
    )

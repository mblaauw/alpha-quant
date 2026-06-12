from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

from alpha_quant.domain.narration import NarrationContext

ReportType = Literal["weekly", "monthly"]


class ReportEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    date: date
    report_type: ReportType
    content: str


def generate_weekly(ctxs: list[NarrationContext], end_date: date) -> ReportEntry:
    start_date = end_date
    for ctx in ctxs:
        if ctx.date < start_date:
            start_date = ctx.date

    total_scored = sum(c.candidates_scored for c in ctxs)
    total_blocked = sum(c.candidates_blocked for c in ctxs)
    total_promoted = sum(c.candidates_promoted for c in ctxs)
    avg_equity = sum(c.equity for c in ctxs) / len(ctxs) if ctxs else 0.0
    end_equity = ctxs[-1].equity if ctxs else 0.0
    start_equity = ctxs[0].equity if ctxs else 0.0
    weekly_return = ((end_equity - start_equity) / start_equity * 100) if start_equity > 0 else 0.0
    last_ctx = ctxs[-1] if ctxs else None

    sections: list[str] = []
    sections.append(f"# Weekly Report — {start_date.isoformat()} to {end_date.isoformat()}\n")

    sections.append("## Performance\n")
    sections.append(f"- Start equity: **${start_equity:,.2f}**\n")
    sections.append(f"- End equity: **${end_equity:,.2f}**\n")
    sections.append(f"- Weekly return: **{weekly_return:+.2f}%**\n")
    sections.append(f"- Average equity: **${avg_equity:,.2f}**\n")

    sections.append("## Candidate Funnel\n")
    sections.append(f"- Scored: {total_scored}\n")
    sections.append(f"- Blocked: {total_blocked}\n")
    sections.append(f"- Promoted: {total_promoted}\n")

    sections.append("## Portfolio\n")
    sections.append(f"- Open positions: {len(last_ctx.positions) if last_ctx else 0}\n")
    if last_ctx:
        cash_pct = last_ctx.cash / last_ctx.equity * 100 if last_ctx.equity > 0 else 0.0
        sections.append(f"- Cash: ${last_ctx.cash:,.2f} ({cash_pct:.0f}%)\n")

    sections.append("## Risk\n")
    sections.append(f"- Regime: **{last_ctx.regime if last_ctx else 'unknown'}**\n")
    if last_ctx:
        degraded = [s for s, h in last_ctx.data_health.items() if not h]
        if degraded:
            sections.append(f"- Degraded sources: {', '.join(degraded)}\n")
        else:
            sections.append("- All data sources healthy.\n")

    return ReportEntry(
        date=end_date,
        report_type="weekly",
        content="".join(sections),
    )


def generate_monthly(ctxs: list[NarrationContext], end_date: date) -> ReportEntry:
    start_date = end_date
    for ctx in ctxs:
        if ctx.date < start_date:
            start_date = ctx.date

    total_scored = sum(c.candidates_scored for c in ctxs)
    total_blocked = sum(c.candidates_blocked for c in ctxs)
    total_promoted = sum(c.candidates_promoted for c in ctxs)
    end_equity = ctxs[-1].equity if ctxs else 0.0
    start_equity = ctxs[0].equity if ctxs else 0.0
    monthly_return = ((end_equity - start_equity) / start_equity * 100) if start_equity > 0 else 0.0
    last_ctx = ctxs[-1] if ctxs else None

    turnover = total_promoted
    estimated_cost = turnover * 10.0 * 2

    sections: list[str] = []
    sections.append(f"# Monthly Report — {start_date.isoformat()} to {end_date.isoformat()}\n")

    sections.append("## Performance Summary\n")
    sections.append(f"- Start equity: **${start_equity:,.2f}**\n")
    sections.append(f"- End equity: **${end_equity:,.2f}**\n")
    sections.append(f"- Monthly return: **{monthly_return:+.2f}%**\n")

    sections.append("## Activity\n")
    sections.append(f"- Candidates scored: {total_scored}\n")
    sections.append(f"- Candidates blocked: {total_blocked}\n")
    sections.append(f"- Candidates promoted: {total_promoted}\n")
    sections.append(f"- Estimated turnover: {turnover} trades\n")

    sections.append("## Cost Drag\n")
    sections.append(f"- Estimated round-trip cost: **${estimated_cost:.0f}**\n")
    sections.append(
        f"- As % of equity: **{estimated_cost / end_equity * 100:.2f}%**\n"
        if end_equity > 0
        else "-\n"
    )

    sections.append("## Portfolio\n")
    if last_ctx:
        sections.append(f"- Open positions: {len(last_ctx.positions)}\n")
        cash_pct = last_ctx.cash / last_ctx.equity * 100 if last_ctx.equity > 0 else 0.0
        sections.append(f"- Cash: ${last_ctx.cash:,.2f} ({cash_pct:.0f}%)\n")
        sections.append(f"- Regime: **{last_ctx.regime}**\n")

    sections.append("## Caveat\n")
    sections.append(
        "Past performance does not guarantee future results. "
        "This is a systematic quantitative strategy and may "
        "underperform during regime changes or black-swan events.\n"
    )

    return ReportEntry(
        date=end_date,
        report_type="monthly",
        content="".join(sections),
    )

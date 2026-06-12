from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from alpha_quant.domain.narration import NarrationContext


class JournalEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    date: date
    content: str


def generate_journal(ctx: NarrationContext) -> JournalEntry:
    sections: list[str] = []

    sections.append(f"# Daily Journal — {ctx.date.isoformat()}\n")

    # Market Overview
    sections.append("## Market Overview\n")
    sections.append(f"Regime: **{ctx.regime}**\n")

    # Data Health
    sections.append("## Data Health\n")
    degraded = [src for src, healthy in ctx.data_health.items() if not healthy]
    if degraded:
        sections.append(f"Degraded sources: {', '.join(degraded)}\n")
    else:
        sections.append("All data sources healthy.\n")

    # Today's Actions
    sections.append("## Today's Actions\n")
    if ctx.candidates_promoted > 0:
        sections.append(f"**{ctx.candidates_promoted}** new positions entered.\n")
    else:
        sections.append("No new positions entered.\n")

    # Non-Actions (negative-space narration)
    sections.append("## Non-Actions\n")
    reasons: list[str] = []
    if ctx.candidates_scored == 0:
        reasons.append("No candidates passed initial scoring.")
    if ctx.candidates_blocked > 0:
        reasons.append(f"{ctx.candidates_blocked} candidates were blocked by gates.")
    if ctx.regime != "RISK_ON":
        reasons.append(f"Regime is {ctx.regime} — reduced allocation.")
    if ctx.cash >= ctx.equity * 0.95:
        reasons.append("Mostly in cash — no high-conviction opportunities met criteria.")
    if not reasons:
        reasons.append("All candidates processed normally.")
    for r in reasons:
        sections.append(f"- {r}\n")

    # Risk Map
    sections.append("## Risk Map\n")
    if ctx.positions:
        sections.append("| Symbol | Shares | Entry | Current | P&L | Stop | Risk% |\n")
        sections.append("|--------|--------|-------|---------|-----|------|-------|\n")
        for p in ctx.positions:
            pl = f"${p.unrealized_pl:+,.0f}" if p.unrealized_pl is not None else "—"
            stop = f"${p.stop_price:.2f}" if p.stop_price is not None else "—"
            risk = f"{p.risk_pct:.1f}%" if p.risk_pct is not None else "—"
            sections.append(
                f"| {p.symbol} | {p.shares:.0f} | ${p.entry_price:.2f}"
                f" | ${p.current_price:.2f} | {pl} | {stop} | {risk} |\n"
            )
    else:
        sections.append("No open positions.\n")

    # Key Numbers
    sections.append("## Key Numbers\n")
    sections.append(f"- Equity: **${ctx.equity:,.2f}**\n")
    sections.append(f"- Cash: **${ctx.cash:,.2f}**\n")
    sections.append(f"- Positions: **{len(ctx.positions)}**\n")
    sections.append(f"- Market exposure: **{1 - ctx.cash / ctx.equity:.1%}**\n")

    # Concept of Day
    sections.append("## Concept of Day\n")
    sections.append(f"*{ctx.concept_of_day or 'No concept selected'}*\n")

    return JournalEntry(
        date=ctx.date,
        content="".join(sections),
    )

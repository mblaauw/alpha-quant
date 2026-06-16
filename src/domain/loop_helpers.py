"""Pure domain functions extracted from app/_loop.py.

These functions operate solely on domain models with no I/O or port calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from domain.ablation import AblationConfig
from domain.blackout import check as check_blackout
from domain.crowding import evaluate as evaluate_crowding
from domain.fundamental import evaluate as evaluate_fundamental
from domain.insider_signal import evaluate as evaluate_insider
from domain.models import (
    Bar,
    Candidate,
    EarningsEntry,
    FundamentalsSnapshot,
    IndicatorState,
    InsiderTransaction,
    MentionCount,
    Position,
)
from domain.risk import RiskAction, RiskConfig, evaluate_stops, evaluate_time_stop
from domain.scoring import compute_composite
from domain.sizing import PositionSize, SizingConfig, size_position
from domain.technical import momentum_score
from domain.technical import score as score_technical

# --- Mechanism data & shared decide step ---


@dataclass
class MechanismData:
    fundamentals: dict[str, FundamentalsSnapshot | None] = field(default_factory=dict)
    insider_txns: dict[str, list[InsiderTransaction]] = field(default_factory=dict)
    mentions: dict[str, list[MentionCount]] = field(default_factory=dict)
    earnings: dict[str, list[EarningsEntry]] = field(default_factory=dict)
    blocked_until: dict[str, date] = field(default_factory=dict)


# --- Bar lookups ---


def get_bar_for_date(
    all_bars: dict[str, list[Bar]],
    symbol: str,
    dt: date,
) -> Bar | None:
    for b in all_bars.get(symbol, []):
        if b.date == dt:
            return b
    return None


def get_date_bars(
    all_bars: dict[str, list[Bar]],
    dt: date,
) -> dict[str, Bar]:
    result: dict[str, Bar] = {}
    for symbol, bars in all_bars.items():
        for b in bars:
            if b.date == dt:
                result[symbol] = b
                break
    return result


def bars_up_to(
    all_bars: dict[str, list[Bar]],
    symbol: str,
    dt: date,
) -> list[Bar]:
    return [b for b in all_bars.get(symbol, []) if b.date <= dt]


# --- Technical helpers ---


def compute_atr(
    state: IndicatorState | None,
    price: float,
    default_pct: float = 0.02,
) -> float:
    atr = state.values.get("atr", price * default_pct) if state else price * default_pct
    if np.isnan(atr) or atr <= 0:
        atr = price * default_pct
    return atr


# --- Risk ---


def evaluate_risk_actions(
    position: Position,
    bar: Bar,
    state: IndicatorState | None,
    risk_config: RiskConfig,
    current_date: date,
) -> list[RiskAction]:
    atr = state.values.get("atr", 0.0) if state else 0.0
    if np.isnan(atr):
        atr = 0.0
    entry_date = position.entry_date if position.entry_date is not None else current_date
    highest_ever = max(
        position.high_since_entry or position.entry_price or 0.0,
        bar.high,
    )
    actions = evaluate_stops(position, bar, atr, highest_ever, risk_config)
    actions.extend(evaluate_time_stop(position, entry_date, current_date, risk_config))
    return actions


# --- Scoring ---


def score_candidate(
    symbol: str,
    bars_to_date: list[Bar],
    bar: Bar,
    state: IndicatorState,
    dt: date,
    regime: str,
) -> Candidate:
    tech = score_technical(bars_to_date, state)
    momentum_scr = momentum_score(bars_to_date, bar.close)
    tech_scr = tech.score
    composite = compute_composite({"technical": tech_scr, "momentum": momentum_scr})
    return Candidate(
        symbol=symbol,
        date=dt,
        scores={"technical": tech_scr, "momentum": momentum_scr},
        composite_score=composite,
        regime=regime,
        gate_results={"fundamental": True, "blackout": True},
    )


# --- Sizing ---


def size_entry(
    equity: float,
    price: float,
    atr_val: float,
    regime_mult: float,
    sizing_config: SizingConfig,
) -> PositionSize | None:
    sized = size_position(equity, price, atr_val, regime_mult, 1.0, sizing_config)
    if sized.shares <= 0:
        return None
    return sized


# --- Mechanism evaluation ---


def _compute_z_score(
    symbol: str,
    mentions: list[MentionCount],
    as_of_date: date,
    window: int = 21,
) -> float | None:
    cutoff = as_of_date - timedelta(days=window)
    recent = [m for m in mentions if cutoff < m.mention_date <= as_of_date]
    if len(recent) < 5:
        return None
    counts = [float(m.count) for m in recent if m.mention_date != as_of_date]
    today_counts = [m.count for m in recent if m.mention_date == as_of_date]
    if len(counts) < 5 or not today_counts:
        return None
    today = float(sum(today_counts)) / len(today_counts)
    mean = np.mean(counts)
    std = np.std(counts)
    if std < 1e-6:
        return None
    return float((today - mean) / std)


def evaluate_candidate_mechanisms(
    symbol: str,
    run_date: date,
    data: MechanismData,
    ablation: AblationConfig | None = None,
) -> tuple[dict[str, float], dict[str, bool], str | None]:
    """Apply M4/M5/M6/M7 mechanisms.

    Returns (additional_scores, gate_results, block_reason).
    AblationConfig can disable M5 (insider) and M6 (crowding) gates.
    """
    ab = ablation or AblationConfig()
    additional_scores: dict[str, float] = {}
    gate_results: dict[str, bool] = {
        "fundamental": True,
        "insider": True,
        "crowding": True,
        "blackout": True,
    }
    block_reason: str | None = None

    # M4: Fundamental quality
    fund_snap = data.fundamentals.get(symbol)
    if fund_snap is not None:
        verdict = evaluate_fundamental(fund_snap)
        if not verdict.passed:
            gate_results["fundamental"] = False
            block_reason = verdict.reason
            return additional_scores, gate_results, block_reason
        if not verdict.passed_degraded:
            additional_scores["quality"] = 1.0

    # M7: Earnings blackout
    earnings = data.earnings.get(symbol, [])
    if earnings:
        verdict = check_blackout(symbol, run_date, earnings, window_days=3)
        if verdict == "BLOCK":
            gate_results["blackout"] = False
            block_reason = "earnings_blackout"
            return additional_scores, gate_results, block_reason

    # M5: Insider signal (skipped when disabled)
    if not ab.disable_insider:
        txns = data.insider_txns.get(symbol, [])
        if txns:
            fund_snap = data.fundamentals.get(symbol)
            market_cap = fund_snap.market_cap if fund_snap else None
            insider_v = evaluate_insider(symbol, txns, run_date, market_cap=market_cap)
            additional_scores["insider"] = insider_v.score
            if insider_v.score < 0:
                gate_results["insider"] = False
                block_reason = insider_v.reason or "negative_insider_signal"
                return additional_scores, gate_results, block_reason

    # M6: Crowding veto (skipped when disabled)
    if not ab.disable_crowding_veto:
        mentions = data.mentions.get(symbol, [])
        if mentions:
            blocked_until = data.blocked_until.get(symbol)
            z = _compute_z_score(symbol, mentions, run_date)
            verdict = evaluate_crowding(z, blocked_until, run_date)
            if verdict.blocked:
                gate_results["crowding"] = False
                block_reason = verdict.reason or "crowding_veto"
                return additional_scores, gate_results, block_reason
            if verdict.blocked_until is not None:
                data.blocked_until[symbol] = verdict.blocked_until

    return additional_scores, gate_results, None

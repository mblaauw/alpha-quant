from __future__ import annotations

from datetime import date

import numpy as np

from alpha_quant.domain.models import (
    Bar,
    Candidate,
    IndicatorState,
    Position,
)
from alpha_quant.domain.regime import REGIME_MULTIPLIERS
from alpha_quant.domain.regime import detect as detect_regime
from alpha_quant.domain.risk import RiskAction, RiskConfig, evaluate_stops, evaluate_time_stop
from alpha_quant.domain.sizing import PositionSize, SizingConfig, size_position
from alpha_quant.domain.technical import momentum_score
from alpha_quant.domain.technical import score as score_technical
from alpha_quant.ports.store import Store


def ensure_spy(symbols: list[str]) -> list[str]:
    syms = list(symbols)
    if "SPY" not in syms:
        syms.append("SPY")
    return syms


def load_all_bars(
    store: Store,
    symbols: list[str],
    start: date,
    end: date,
) -> dict[str, list[Bar]]:
    all_bars: dict[str, list[Bar]] = {}
    for symbol in symbols:
        bars = store.load_bars(symbol, start, end)
        if bars:
            all_bars[symbol] = bars
    return all_bars


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


def detect_regime_and_multiplier(
    spy_state: IndicatorState | None,
) -> tuple[str, float]:
    if spy_state is not None:
        regime = detect_regime(spy_state, vix_level=15.0, breadth=0.6)
    else:
        regime = "CAUTION"
    return regime, REGIME_MULTIPLIERS.get(regime, 0.5)


def compute_atr(
    state: IndicatorState | None,
    price: float,
    default_pct: float = 0.02,
) -> float:
    atr = state.values.get("atr", price * default_pct) if state else price * default_pct
    if np.isnan(atr) or atr <= 0:
        atr = price * default_pct
    return atr


def evaluate_risk_actions(
    position: Position,
    bar: Bar,
    state: IndicatorState | None,
    risk_config: RiskConfig,
    entry_date: date,
    current_date: date,
) -> list[RiskAction]:
    atr = state.values.get("atr", 0.0) if state else 0.0
    if np.isnan(atr):
        atr = 0.0
    highest = max(position.entry_price or 0.0, bar.high)
    actions = evaluate_stops(position, bar, atr, highest, risk_config)
    actions.extend(evaluate_time_stop(position, entry_date, current_date, risk_config))
    return actions


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
    composite = 0.70 * tech_scr + 0.30 * momentum_scr
    return Candidate(
        symbol=symbol,
        date=dt,
        scores={"technical": tech_scr, "momentum": momentum_scr},
        composite_score=min(1.0, composite),
        regime=regime,
        gate_results={"fundamental": True, "blackout": True},
    )


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

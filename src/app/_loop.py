from __future__ import annotations

from datetime import date

import numpy as np

from domain.ablation import AblationConfig
from domain.loop_helpers import (  # noqa: F401 — re-export for consumers
    MechanismData,
    bars_up_to,
    compute_atr,
    evaluate_candidate_mechanisms,
    evaluate_risk_actions,
    get_bar_for_date,
    get_date_bars,
    score_candidate,
    size_entry,
)
from domain.models import Bar, Candidate, IndicatorState
from domain.regime import REGIME_MULTIPLIERS
from domain.regime import detect as detect_regime


def ensure_spy(symbols: list[str]) -> list[str]:
    syms = list(symbols)
    if "SPY" not in syms:
        syms.append("SPY")
    return syms


def detect_regime_and_multiplier(
    spy_state: IndicatorState | None,
) -> tuple[str, float]:
    if spy_state is not None:
        regime = detect_regime(spy_state, vix_level=15.0, breadth=0.6)
    else:
        regime = "CAUTION"
    return regime, REGIME_MULTIPLIERS.get(regime, 0.5)


def decide_candidates(
    symbols: list[str],
    all_bars: dict[str, list[Bar]],
    indicator_states: dict[str, IndicatorState],
    run_date: date,
    regime: str,
    mechanism_data: MechanismData | None = None,
    ablation: AblationConfig | None = None,
) -> list[Candidate]:
    """Shared decide step used by pipeline.run and backtest.run_backtest.

    Returns candidates that pass all mechanism gates (M4/M5/M6/M7).
    Candidates blocked by any mechanism are excluded.
    Caller should emit CandidateScored for surviving candidates
    and CandidateBlocked for blocked ones (with mechanism data).
    AblationConfig can disable M5 (insider) and M6 (crowding) gates.
    """
    data = mechanism_data or MechanismData()
    result: list[Candidate] = []

    for symbol in symbols:
        bar = get_bar_for_date(all_bars, symbol, run_date)
        state = indicator_states.get(symbol)
        if bar is None or state is None:
            continue
        vals = state.values
        if np.isnan(vals.get("rsi", np.nan)):
            continue

        bars_to_date = bars_up_to(all_bars, symbol, run_date)
        cand = score_candidate(symbol, bars_to_date, bar, state, run_date, regime)

        extra_scores, gate_results, block_reason = evaluate_candidate_mechanisms(
            symbol,
            run_date,
            data,
            ablation,
        )

        fund_snap = data.fundamentals.get(symbol)
        sector = fund_snap.sector if fund_snap else cand.sector

        all_gates_pass = all(gate_results.values())

        if not all_gates_pass:
            gate_block = next(gate for gate, passed in gate_results.items() if not passed)
            result.append(
                cand.model_copy(
                    update={
                        "sector": sector,
                        "scores": {**cand.scores, **extra_scores},
                        "gate_results": gate_results,
                        "block_reason": block_reason or f"blocked_by_{gate_block}",
                    }
                )
            )
        else:
            updated = cand.model_copy(
                update={
                    "sector": sector,
                    "scores": {**cand.scores, **extra_scores},
                    "gate_results": gate_results,
                }
            )
            result.append(updated)

    return result

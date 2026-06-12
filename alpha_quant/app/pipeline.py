from __future__ import annotations

import uuid
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, date, datetime

import numpy as np

from alpha_quant.domain.derive import backfill_indicator_state
from alpha_quant.domain.events import (
    CandidateBlocked,
    CandidatePromoted,
    CandidateScored,
    ConsistencyViolation,
    PipelineRunCompleted,
    PipelineRunStarted,
    RegimeChanged,
    SourceDegraded,
    StopAdjusted,
)
from alpha_quant.domain.fills import FillConfig, fill_stop_loss
from alpha_quant.domain.invariants import InvariantViolation
from alpha_quant.domain.models import Bar, Candidate, Decision, Fill, IndicatorState, Position
from alpha_quant.domain.ranking import rank as rank_candidates
from alpha_quant.domain.regime import REGIME_MULTIPLIERS
from alpha_quant.domain.regime import detect as detect_regime
from alpha_quant.domain.risk import RiskConfig, evaluate_stops, evaluate_time_stop
from alpha_quant.domain.sizing import SizingConfig, size_position
from alpha_quant.domain.technical import momentum_score
from alpha_quant.domain.technical import score as score_technical
from alpha_quant.ports.store import Store

_LOOKBACK_DAYS = 400
_REGIME_CACHE: dict[str, str] = {}


@dataclass
class PipelineConfig:
    run_id: str = ""
    max_positions: int = 10
    lookback_days: int = 400


@dataclass
class RunResult:
    run_id: str
    date: date
    decisions: list[Decision]
    fills: list[Fill]
    events: list[object]
    violations: list[InvariantViolation]
    prev_equity: float | None = None
    new_equity: float | None = None


def run(
    run_date: date,
    store: Store,
    universe: list[str],
    config: PipelineConfig | None = None,
    fill_config: FillConfig | None = None,
    risk_config: RiskConfig | None = None,
    sizing_config: SizingConfig | None = None,
    prev_equity: float | None = None,
) -> RunResult:
    cfg = config or PipelineConfig()
    fc = fill_config or FillConfig()
    rc = risk_config or RiskConfig()
    sc = sizing_config or SizingConfig()

    run_id = cfg.run_id or uuid.uuid4().hex[:16]
    events: list[object] = []
    decisions: list[Decision] = []
    fills: list[Fill] = []

    now = datetime.now(UTC)
    events.append(
        PipelineRunStarted(
            event_id=uuid.uuid4().hex[:16],
            timestamp=now,
            run_id=run_id,
            source="pipeline",
            mode="daily",
        )
    )

    lookback_start = date.fromordinal(run_date.toordinal() - cfg.lookback_days)
    symbols = list(universe)
    if "SPY" not in symbols:
        symbols.append("SPY")

    all_bars: dict[str, list[Bar]] = {}
    for symbol in symbols:
        try:
            bars = store.load_bars(symbol, lookback_start, run_date)
            if bars:
                all_bars[symbol] = bars
        except Exception:
            events.append(
                SourceDegraded(
                    event_id=uuid.uuid4().hex[:16],
                    timestamp=datetime.now(UTC),
                    run_id=run_id,
                    source="pipeline",
                    source_name=symbol,
                    fallback="skip",
                )
            )

    if not all_bars.get("SPY"):
        duration = (datetime.now(UTC) - now).total_seconds()
        events.append(
            PipelineRunCompleted(
                event_id=uuid.uuid4().hex[:16],
                timestamp=datetime.now(UTC),
                run_id=run_id,
                source="pipeline",
                duration_s=duration,
                status="no_spy_data",
            )
        )
        return RunResult(
            run_id=run_id,
            date=run_date,
            decisions=[],
            fills=[],
            events=events,
            violations=[],
        )

    # --- 3. Derive indicators ---
    indicator_states: dict[str, IndicatorState] = {}
    for symbol, bars in all_bars.items():
        if bars:
            with suppress(Exception):
                indicator_states[symbol] = backfill_indicator_state(bars)

    # --- 4. Regime ---
    spy_state = indicator_states.get("SPY")
    prev_regime = _REGIME_CACHE.get("current", "CAUTION")
    if spy_state is not None:
        regime = detect_regime(spy_state, vix_level=15.0, breadth=0.6)
    else:
        regime = "CAUTION"
    _REGIME_CACHE["current"] = regime
    if regime != prev_regime:
        events.append(
            RegimeChanged(
                event_id=uuid.uuid4().hex[:16],
                timestamp=datetime.now(UTC),
                run_id=run_id,
                source="pipeline",
                previous=prev_regime,
                current=regime,
            )
        )
    regime_mult = REGIME_MULTIPLIERS.get(regime, 0.5)

    prices: dict[str, float] = {}
    for symbol in symbols:
        bars = all_bars.get(symbol, [])
        if bars:
            prices[symbol] = bars[-1].close

    # --- 5. Risk exits ---
    existing_positions = store.load_positions()
    positions_map: dict[str, Position] = {p.symbol: p for p in existing_positions}
    violations: list[InvariantViolation] = []
    cash_adjust: float = 0.0

    for sym, pos in positions_map.items():
        if pos.quantity <= 0:
            continue
        bar = None
        for b in all_bars.get(sym, []):
            if b.date == run_date:
                bar = b
                break
        if bar is None:
            continue
        state = indicator_states.get(sym)
        atr = state.values.get("atr", 0.0) if state else 0.0
        if np.isnan(atr):
            atr = 0.0
        highest = max(pos.entry_price or 0.0, bar.high)

        risk_actions = evaluate_stops(pos, bar, atr, highest, rc)
        risk_actions.extend(evaluate_time_stop(pos, run_date, run_date, rc))

        for action in risk_actions:
            exit_order_id = f"{sym}_exit_{run_id[:8]}"
            exit_fill = fill_stop_loss(pos, bar, exit_order_id, config=fc)
            if exit_fill is None:
                sell_price = max(bar.open * 0.99, bar.low)
                exit_fill = Fill(
                    fill_id=uuid.uuid4().hex[:16],
                    order_id=exit_order_id,
                    symbol=sym,
                    quantity=-pos.quantity,
                    price=round(sell_price, 2),
                    timestamp=datetime.now(UTC),
                )

            proceeds = round(abs(exit_fill.quantity) * exit_fill.price, 2)
            cash_adjust += proceeds
            pl = round((exit_fill.price - pos.avg_cost) * abs(exit_fill.quantity), 2)
            updated = pos.model_copy(
                update={
                    "quantity": 0,
                    "realized_pl": (pos.realized_pl or 0) + pl,
                    "current_price": exit_fill.price,
                    "market_value": 0.0,
                }
            )
            store.save_position(updated)
            store.save_fill(exit_fill)
            fills.append(exit_fill)
            decisions.append(
                Decision(
                    symbol=sym,
                    date=run_date,
                    action="exit",
                    confidence=1.0,
                    reasons=[action.reason],
                    decision_id=uuid.uuid4().hex[:16],
                )
            )
            events.append(
                StopAdjusted(
                    event_id=uuid.uuid4().hex[:16],
                    timestamp=datetime.now(UTC),
                    run_id=run_id,
                    source="pipeline",
                    symbol=sym,
                    old_stop=pos.stop_price or 0.0,
                    new_stop=0.0,
                )
            )

    # --- 6. Decide (score + rank + size) ---
    new_positions_count = len([p for p in store.load_positions() if p.quantity > 0])
    slots = cfg.max_positions - new_positions_count

    entry_decisions: list[Decision] = []
    if slots > 0 and regime_mult > 0:
        candidates: list[Candidate] = []
        for symbol in universe:
            bar = None
            for b in all_bars.get(symbol, []):
                if b.date == run_date:
                    bar = b
                    break
            state = indicator_states.get(symbol)
            if bar is None or state is None:
                continue
            vals = state.values
            if np.isnan(vals.get("rsi", np.nan)):
                continue

            bars_to_date = [b for b in all_bars.get(symbol, []) if b.date <= run_date]
            tech = score_technical(bars_to_date, state)
            mom = momentum_score(bars_to_date, bar.close)
            tech_scr = tech.score
            composite = 0.70 * tech_scr + 0.30 * mom
            cscore = min(1.0, composite)

            gate_block: str | None = None
            gate_results: dict[str, bool] = {"fundamental": True, "blackout": True}

            if cscore < 0.5:
                gate_block = "composite_below_threshold"

            if gate_block:
                events.append(
                    CandidateBlocked(
                        event_id=uuid.uuid4().hex[:16],
                        timestamp=datetime.now(UTC),
                        run_id=run_id,
                        source="pipeline",
                        symbol=symbol,
                        reason=gate_block,
                        gate="ranking",
                    )
                )
            else:
                candidates.append(
                    Candidate(
                        symbol=symbol,
                        date=run_date,
                        scores={"technical": tech_scr, "momentum": mom},
                        composite_score=cscore,
                        regime=regime,
                        gate_results=gate_results,
                    )
                )
                events.append(
                    CandidateScored(
                        event_id=uuid.uuid4().hex[:16],
                        timestamp=datetime.now(UTC),
                        run_id=run_id,
                        source="pipeline",
                        symbol=symbol,
                        composite_score=cscore,
                        components={"technical": tech_scr, "momentum": mom},
                    )
                )

        current_positions = [p for p in store.load_positions() if p.quantity > 0]
        ranked = rank_candidates(candidates, cfg.max_positions, len(current_positions))

        for cand in ranked[:slots]:
            bar = None
            for b in all_bars.get(cand.symbol, []):
                if b.date == run_date:
                    bar = b
                    break
            state = indicator_states.get(cand.symbol)
            if bar is None or state is None:
                continue
            price = bar.close
            atr_val = state.values.get("atr", price * 0.02)
            if np.isnan(atr_val) or atr_val <= 0:
                atr_val = price * 0.02

            pop_equity = (prev_equity or 100_000.0) + cash_adjust
            sized = size_position(pop_equity, price, atr_val, regime_mult, 1.0, sc)
            final_shares = sized.shares
            if final_shares <= 0:
                continue
            cost = round(final_shares * price, 2)

            decision_id = uuid.uuid4().hex[:16]
            stop_price = round(price - rc.stop_atr_mult * atr_val, 2)

            pos = Position(
                symbol=cand.symbol,
                quantity=float(final_shares),
                entry_price=price,
                avg_cost=price,
                current_price=price,
                stop_price=stop_price,
                market_value=cost,
                decision_id=decision_id,
            )
            store.save_position(pos)

            entry_decisions.append(
                Decision(
                    decision_id=decision_id,
                    symbol=cand.symbol,
                    date=run_date,
                    action="enter",
                    confidence=cand.composite_score,
                    reasons=["technical_score"],
                )
            )
            events.append(
                CandidatePromoted(
                    event_id=uuid.uuid4().hex[:16],
                    timestamp=datetime.now(UTC),
                    run_id=run_id,
                    source="pipeline",
                    symbol=cand.symbol,
                    score=cand.composite_score,
                    target_weight=round(cost / pop_equity, 4) if pop_equity > 0 else 0.0,
                )
            )

    decisions.extend(entry_decisions)

    # --- Self-consistency ---
    all_positions = store.load_positions()
    for pos in all_positions:
        if pos.market_value is not None and pos.market_value < 0:
            inv = InvariantViolation(
                check="I11_negative_market_value",
                detail=f"{pos.symbol}: market_value={pos.market_value}",
            )
            violations.append(inv)
            events.append(
                ConsistencyViolation(
                    event_id=uuid.uuid4().hex[:16],
                    timestamp=datetime.now(UTC),
                    run_id=run_id,
                    source="pipeline",
                    check=inv.check,
                    detail=inv.detail,
                )
            )

    pop_equity_final = (prev_equity or 100_000.0) + cash_adjust
    has_violations = len(violations) > 0
    duration = (datetime.now(UTC) - now).total_seconds()
    events.append(
        PipelineRunCompleted(
            event_id=uuid.uuid4().hex[:16],
            timestamp=datetime.now(UTC),
            run_id=run_id,
            source="pipeline",
            duration_s=duration,
            status="completed" if not has_violations else "violations",
        )
    )

    return RunResult(
        run_id=run_id,
        date=run_date,
        decisions=decisions,
        fills=fills,
        events=events,
        violations=violations,
        prev_equity=prev_equity,
        new_equity=pop_equity_final,
    )

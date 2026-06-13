from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

import numpy as np
import structlog

from alpha_quant.app._loop import (
    bars_up_to,
    compute_atr,
    detect_regime_and_multiplier,
    ensure_spy,
    evaluate_risk_actions,
    get_bar_for_date,
    score_candidate,
    size_entry,
)
from alpha_quant.app.halt import write_halt
from alpha_quant.domain.ablation import AblationConfig
from alpha_quant.domain.degradation import DegradationStatus, m3_threshold_multiplier
from alpha_quant.domain.derive import backfill_indicator_state
from alpha_quant.domain.events import (
    CandidateBlocked,
    CandidatePromoted,
    CandidateScored,
    ConsistencyViolation,
    DataQuarantined,
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
from alpha_quant.domain.risk import RiskConfig
from alpha_quant.domain.sizing import SizingConfig
from alpha_quant.domain.validate import validate_bars, validate_indicator_state
from alpha_quant.ports.store import Store

logger = structlog.get_logger()

_LOOKBACK_DAYS = 400


@dataclass
class PipelineConfig:
    run_id: str = ""
    max_positions: int = 10
    lookback_days: int = 400
    ablation: AblationConfig | None = None


@dataclass
class RunResult:
    run_id: str
    date: date
    decisions: list[Decision]
    fills: list[Fill]
    events: list[object]
    violations: list[InvariantViolation]
    current_regime: str | None = None
    halted: bool = False
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
    prev_regime: str = "CAUTION",
    degradation: DegradationStatus | None = None,
) -> RunResult:
    cfg = config or PipelineConfig()
    fc = fill_config or FillConfig()
    rc = risk_config or RiskConfig()
    sc = sizing_config or SizingConfig()
    deg = degradation or DegradationStatus()

    run_id = cfg.run_id or uuid.uuid4().hex[:16]
    events: list[object] = []
    decisions: list[Decision] = []
    fills: list[Fill] = []

    now = datetime.now(UTC)
    events.append(
        PipelineRunStarted(
            timestamp=now,
            run_id=run_id,
            source="pipeline",
            mode="daily",
        )
    )

    lookback_start = date.fromordinal(run_date.toordinal() - cfg.lookback_days)
    halted = False
    symbols = ensure_spy(universe)

    all_bars: dict[str, list[Bar]] = {}
    for symbol in symbols:
        try:
            bars = store.load_bars(symbol, lookback_start, run_date)
            if bars:
                all_bars[symbol] = bars
        except Exception:
            logger.exception("bar_load_failed", symbol=symbol)
            events.append(
                SourceDegraded(
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
            halted=halted,
        )

    # --- 2. Validate bars ---
    for symbol, bars in all_bars.items():
        if not bars:
            continue
        results = validate_bars(bars)
        for vr in results:
            events.append(
                DataQuarantined(
                    run_id=run_id,
                    source="pipeline",
                    symbol=symbol,
                    reason=vr.check,
                    detail="; ".join(vr.issues),
                )
            )
            if vr.severity == "HALT":
                halted = True
                write_halt(reason=vr.check, run_id=run_id)

    # --- 3. Derive indicators ---
    indicator_states: dict[str, IndicatorState] = {}
    for symbol, bars in all_bars.items():
        if bars:
            try:
                indicator_states[symbol] = backfill_indicator_state(bars)
            except Exception:
                logger.exception("indicator_backfill_failed", symbol=symbol)

    # --- 3b. Validate indicators ---
    for symbol, state in indicator_states.items():
        results = validate_indicator_state(state)
        for vr in results:
            events.append(
                DataQuarantined(
                    run_id=run_id,
                    source="pipeline",
                    symbol=symbol,
                    reason=vr.check,
                    detail="; ".join(vr.issues),
                )
            )

    # --- 4. Regime ---
    spy_state = indicator_states.get("SPY")
    regime, regime_mult = detect_regime_and_multiplier(spy_state)
    if regime != prev_regime:
        events.append(
            RegimeChanged(
                run_id=run_id,
                source="pipeline",
                previous=prev_regime,
                current=regime,
            )
        )
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
        bar = get_bar_for_date(all_bars, sym, run_date)
        if bar is None:
            continue
        state = indicator_states.get(sym)
        risk_actions = evaluate_risk_actions(pos, bar, state, rc, run_date, run_date)

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
            bar = get_bar_for_date(all_bars, symbol, run_date)
            state = indicator_states.get(symbol)
            if bar is None or state is None:
                continue
            vals = state.values
            if np.isnan(vals.get("rsi", np.nan)):
                continue

            bars_to_date = bars_up_to(all_bars, symbol, run_date)
            cand = score_candidate(symbol, bars_to_date, bar, state, run_date, regime)
            cscore = cand.composite_score

            gate_block: str | None = None
            gate_threshold = 0.5 * m3_threshold_multiplier(deg)

            if cscore < gate_threshold:
                gate_block = "composite_below_threshold"

            if gate_block:
                events.append(
                    CandidateBlocked(
                        run_id=run_id,
                        source="pipeline",
                        symbol=symbol,
                        reason=gate_block,
                        gate="ranking",
                    )
                )
            else:
                candidates.append(cand)
                events.append(
                    CandidateScored(
                        run_id=run_id,
                        source="pipeline",
                        symbol=symbol,
                        composite_score=cscore,
                        components={
                            "technical": cand.scores["technical"],
                            "momentum": cand.scores["momentum"],
                        },
                    )
                )

        current_positions = [p for p in store.load_positions() if p.quantity > 0]
        ranked = rank_candidates(candidates, cfg.max_positions, len(current_positions))

        for cand in ranked[:slots]:
            bar = get_bar_for_date(all_bars, cand.symbol, run_date)
            state = indicator_states.get(cand.symbol)
            if bar is None or state is None:
                continue
            atr_val = compute_atr(state, bar.close)

            pop_equity = (prev_equity or 100_000.0) + cash_adjust
            sized = size_entry(pop_equity, bar.close, atr_val, regime_mult, sc)
            if sized is None:
                continue
            final_shares = sized.shares
            cost = round(final_shares * bar.close, 2)

            decision_id = uuid.uuid4().hex[:16]
            stop_price = round(bar.close - rc.stop_atr_mult * atr_val, 2)

            pos = Position(
                symbol=cand.symbol,
                quantity=float(final_shares),
                entry_price=bar.close,
                avg_cost=bar.close,
                current_price=bar.close,
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
        current_regime=regime,
        halted=halted,
        prev_equity=prev_equity,
        new_equity=pop_equity_final,
    )

from __future__ import annotations

import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime

import structlog

from alpha_quant.contracts.alpha_lake import (
    BarObservation,
    NeutralObservations,
)
from alpha_quant.domain.decision_context import DecisionContext
from alpha_quant.domain.degradation import DegradationStatus, m3_threshold_multiplier
from alpha_quant.domain.events import (
    CandidateBlocked,
    CandidatePromoted,
    CandidateScored,
    ConsistencyViolation,
    DomainEvent,
    DrawdownLadderTripped,
    ErrorOccurred,
    FillBooked,
    PartialTaken,
    PipelineRunCompleted,
    PipelineRunStarted,
    PipelineStepCompleted,
    RegimeChanged,
    StopAdjusted,
    TimeStopTriggered,
)
from alpha_quant.domain.fills import FillConfig, fill_entry_order, fill_stop_loss
from alpha_quant.domain.invariants import InvariantViolation, check_invariants
from alpha_quant.domain.models import (
    Bar,
    Candidate,
    Decision,
    Fill,
    IndicatorState,
    Order,
    PortfolioSnapshot,
    Position,
)
from alpha_quant.domain.policy import (
    attention_policy,
    composite_policy,
    earnings_blackout_policy,
    fundamental_policy,
    insider_policy,
    regime_policy,
    technical_policy,
)
from alpha_quant.domain.policy.regime_policy import Regime as RegimeLiteral
from alpha_quant.domain.ranking import rank as rank_candidates
from alpha_quant.domain.risk import (
    RiskConfig,
    evaluate_daily_loss,
    evaluate_drawdown,
    evaluate_stops,
    evaluate_time_stop,
)
from alpha_quant.domain.sizing import SizingConfig, size_position
from alpha_quant.ports.alpha_lake import AlphaLakeReadPort
from alpha_quant.ports.store import Store


@dataclass
class PipelineConfig:
    run_id: str = ""
    max_positions: int = 10
    lookback_days: int = 400
    ablation: None = None


@dataclass
class RunResult:
    run_id: str
    date: date
    decisions: list[Decision]
    fills: list[Fill]
    events: list[DomainEvent]
    violations: list[InvariantViolation]
    current_regime: str | None = None
    halted: bool = False
    prev_equity: float | None = None
    new_equity: float | None = None


logger = structlog.get_logger()

REGIME_MULTIPLIERS: dict[str, float] = {
    "RISK_ON": 1.0,
    "CAUTION": 0.5,
    "RISK_OFF": 0.0,
}


def _bar_for_date(obs: NeutralObservations, symbol: str, target: date) -> BarObservation | None:
    so = obs.per_symbol.get(symbol)
    if so is None:
        return None
    for b in so.bars:
        if b.effective_date == target:
            return b
    return None


def _make_bar(bar_obs: BarObservation, symbol: str) -> Bar:
    return Bar(
        symbol=symbol,
        date=bar_obs.effective_date,
        open=bar_obs.open,
        high=bar_obs.high,
        low=bar_obs.low,
        close=bar_obs.close,
        volume=bar_obs.volume,
        adj_close=bar_obs.adj_close,
    )


def _prices(obs: NeutralObservations) -> dict[str, float]:
    result: dict[str, float] = {}
    for symbol, so in obs.per_symbol.items():
        if so.price is not None:
            result[symbol] = so.price.latest_close
        elif so.bars:
            result[symbol] = so.bars[-1].close
    return result


def _dollar_atr(obs: NeutralObservations, symbol: str, default_pct: float = 0.02) -> float:
    so = obs.per_symbol.get(symbol)
    if so is None or not so.bars:
        return 0.0
    close = so.bars[-1].close
    if so.technical is not None and so.technical.atr_pct_14 is not None:
        return close * so.technical.atr_pct_14
    return close * default_pct


def _make_state(symbol: str, run_date: date, d_atr: float) -> IndicatorState:
    return IndicatorState(symbol=symbol, date=run_date, values={"atr": d_atr})


def _evaluate_candidate(
    symbol: str,
    ctx: DecisionContext,
    run_date: date,
    regime: RegimeLiteral,
    threshold: float,
    blackout_schedule: earnings_blackout_policy.BlackoutSchedule | None = None,
) -> Candidate | None:
    close = ctx.latest_close()
    if close is None:
        return None

    tech_score = technical_policy.evaluate(ctx)
    mom_score = technical_policy.momentum_score(ctx)
    insider_scr = insider_policy.evaluate(ctx)

    scores: dict[str, float] = {
        "technical": tech_score,
        "momentum": mom_score,
    }
    if insider_scr > 0:
        scores["insider"] = insider_scr

    composite = composite_policy.compute_composite(scores)

    gate_results: dict[str, bool] = {}
    block_reason: str | None = None

    fund_pass = fundamental_policy.evaluate(ctx)
    gate_results["fundamental"] = fund_pass
    if not fund_pass:
        block_reason = "blocked_by_fundamental"

    if block_reason is None and not attention_policy.evaluate(ctx):
        gate_results["attention"] = False
        block_reason = "blocked_by_attention"
    else:
        gate_results["attention"] = True

    if block_reason is None:
        if blackout_schedule is not None:
            if blackout_schedule.is_blocked(symbol, ctx, as_of=run_date):
                gate_results["earnings_blackout"] = False
                block_reason = "blocked_by_earnings_blackout"
            else:
                gate_results["earnings_blackout"] = True
        else:
            gate_results["earnings_blackout"] = True

    if composite < threshold:
        block_reason = block_reason or "composite_below_threshold"

    return Candidate(
        symbol=symbol,
        date=run_date,
        scores=scores,
        composite_score=composite,
        gate_results=gate_results,
        block_reason=block_reason,
        regime=regime,
    )


@contextmanager
def _time_step(
    step_name: str,
    run_id: str,
    events: list[DomainEvent],
    symbols_processed: int = 0,
    items_processed: int = 0,
):
    start = datetime.now(UTC)
    try:
        yield
    finally:
        duration = (datetime.now(UTC) - start).total_seconds()
        events.append(
            PipelineStepCompleted(
                run_id=run_id,
                source="pipeline",
                step_name=step_name,
                duration_s=duration,
                symbols_processed=symbols_processed,
                items_processed=items_processed,
            )
        )


def run_v2(
    run_date: date,
    store: Store,
    universe: list[str],
    alpha_lake: AlphaLakeReadPort,
    config: PipelineConfig,
    fill_config: FillConfig,
    risk_config: RiskConfig,
    sizing_config: SizingConfig,
    prev_equity: float | None = None,
    prev_regime: str | None = None,
    staleness_days: int | None = None,
) -> RunResult:
    cfg = config or PipelineConfig()
    fc = fill_config or FillConfig()
    rc = risk_config or RiskConfig()
    sc = sizing_config or SizingConfig()

    deg = DegradationStatus()
    run_id = cfg.run_id or uuid.uuid4().hex[:16]
    events: list[DomainEvent] = []
    decisions: list[Decision] = []
    fills: list[Fill] = []
    now = datetime.now(UTC)

    events.append(PipelineRunStarted(timestamp=now, run_id=run_id, source="pipeline", mode="daily"))

    symbols = list(universe)
    if "SPY" not in symbols:
        symbols.append("SPY")

    halted = False

    as_of = datetime.combine(run_date, datetime.min.time(), tzinfo=UTC)

    with _time_step("decision_panel", run_id, events, symbols_processed=len(symbols)):
        try:
            health = alpha_lake.health()
            if health.status in ("error", "unreachable"):
                logger.warning("alpha_lake_health_failed", status=health.status)
        except Exception:
            logger.warning("alpha_lake_health_check_failed")

        try:
            obs = alpha_lake.read_observations(symbols, as_of)
        except Exception:
            logger.exception("alpha_lake_decision_panel_load_failed")
            duration = (datetime.now(UTC) - now).total_seconds()
            events.append(
                PipelineRunCompleted(
                    run_id=run_id, source="pipeline", duration_s=duration, status="no_data"
                )
            )
            return RunResult(
                run_id=run_id,
                date=run_date,
                decisions=[],
                fills=[],
                events=events,
                violations=[],
                halted=True,
            )

    prices = _prices(obs)

    spy_so = obs.per_symbol.get("SPY")
    if spy_so is None or not spy_so.bars:
        duration = (datetime.now(UTC) - now).total_seconds()
        events.append(
            PipelineRunCompleted(
                run_id=run_id, source="pipeline", duration_s=duration, status="no_spy_data"
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

    spy_ctx = DecisionContext(obs, "SPY")
    regime: RegimeLiteral = regime_policy.detect(spy_ctx)
    regime_mult = REGIME_MULTIPLIERS.get(regime, 0.5)
    if regime != prev_regime:
        events.append(
            RegimeChanged(run_id=run_id, source="pipeline", previous=prev_regime, current=regime)
        )

    existing_positions = store.load_positions()
    positions_map: dict[str, Position] = {p.symbol: p for p in existing_positions}
    violations: list[InvariantViolation] = []
    cash_adjust: float = 0.0

    with _time_step("risk", run_id, events, symbols_processed=len(positions_map)):
        _ts_risk = datetime.now(UTC)
        for sym, pos in positions_map.items():
            if pos.quantity <= 0:
                continue
            bar_obs = _bar_for_date(obs, sym, run_date)
            if bar_obs is None:
                continue
            bar = _make_bar(bar_obs, sym)

            d_atr = _dollar_atr(obs, sym)
            entry_date = pos.entry_date if pos.entry_date is not None else run_date
            highest_ever = max(
                pos.high_since_entry or pos.entry_price or 0.0,
                bar.high,
            )
            actions = evaluate_stops(pos, bar, d_atr, highest_ever, rc)
            actions.extend(evaluate_time_stop(pos, entry_date, run_date, rc))

            for action in actions:
                if action.action_type == "trail_stop":
                    updated_stop = pos.model_copy(
                        update={
                            "stop_price": action.price,
                            "high_since_entry": max(
                                pos.high_since_entry or pos.entry_price or 0.0,
                                bar.high,
                            ),
                        }
                    )
                    store.save_position(updated_stop)
                    events.append(
                        StopAdjusted(
                            run_id=run_id,
                            source="pipeline",
                            symbol=sym,
                            old_stop=pos.stop_price or 0.0,
                            new_stop=action.price or 0.0,
                        )
                    )
                    continue

                if action.action_type == "partial_take":
                    reduce_qty = abs(action.shares)
                    remaining = pos.quantity - reduce_qty
                    pl = round((action.price or bar.close) - pos.avg_cost, 2) * reduce_qty
                    updated = pos.model_copy(
                        update={
                            "quantity": remaining,
                            "realized_pl": (pos.realized_pl or 0) + pl,
                            "current_price": action.price or bar.close,
                            "market_value": remaining * (action.price or bar.close),
                            "partial_taken": True,
                            "high_since_entry": max(
                                pos.high_since_entry or pos.entry_price or 0.0,
                                bar.high,
                            ),
                        }
                    )
                    store.save_position(updated)
                    events.append(
                        PartialTaken(
                            run_id=run_id,
                            source="pipeline",
                            symbol=sym,
                            quantity=reduce_qty,
                            price=action.price or bar.close,
                        )
                    )
                    proceed = round(reduce_qty * (action.price or bar.close), 2)
                    cash_adjust += proceed
                    decisions.append(
                        Decision(
                            symbol=sym,
                            date=run_date,
                            action="partial_take",
                            confidence=1.0,
                            reasons=[action.reason],
                            decision_id=uuid.uuid4().hex[:16],
                        )
                    )
                    continue

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
                        "high_since_entry": max(
                            pos.high_since_entry or pos.entry_price or 0.0,
                            bar.high,
                        ),
                    }
                )
                store.save_position(updated)
                store.save_fill(exit_fill)
                fills.append(exit_fill)
                events.append(FillBooked(run_id=run_id, source="pipeline", fill=exit_fill))
                if action.action_type == "time_stop":
                    entry_date_pos = pos.entry_date or run_date
                    events.append(
                        TimeStopTriggered(
                            run_id=run_id,
                            source="pipeline",
                            symbol=sym,
                            days_held=(run_date - entry_date_pos).days,
                        )
                    )
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

        equity_snapshots = store.load_portfolio_snapshots()
        equity_values = [s.equity for s in equity_snapshots]
        dd_verdict = evaluate_drawdown(equity_values, rc)
        if dd_verdict.multiplier < 1.0 and equity_values:
            peak = max(equity_values)
            current = equity_values[-1]
            dd_pct = (peak - current) / peak if peak > 0 else 0.0
            events.append(
                DrawdownLadderTripped(
                    run_id=run_id,
                    source="pipeline",
                    drawdown_pct=round(dd_pct * 100, 2),
                    action=f"multiplier reduced to {dd_verdict.multiplier}",
                )
            )

        events.append(
            PipelineStepCompleted(
                run_id=run_id,
                source="pipeline",
                step_name="risk",
                duration_s=(datetime.now(UTC) - _ts_risk).total_seconds(),
                symbols_processed=len(positions_map),
            )
        )

    _ts_decide = datetime.now(UTC)
    new_positions_count = len([p for p in store.load_positions() if p.quantity > 0])
    slots = cfg.max_positions - new_positions_count

    gate_threshold = 0.5 * m3_threshold_multiplier(deg)

    entry_decisions: list[Decision] = []
    effective_mult = regime_mult * dd_verdict.multiplier
    entry_cost: float = 0.0

    blackout_schedule = earnings_blackout_policy.BlackoutSchedule()

    if slots > 0 and effective_mult > 0:
        candidates: list[Candidate] = []

        for symbol in symbols:
            so = obs.per_symbol.get(symbol)
            if so is None or not so.bars:
                continue

            if staleness_days is not None and so.bars:
                last_bar_date = so.bars[-1].effective_date
                age_days = (run_date - last_bar_date).days
                if age_days > staleness_days:
                    events.append(
                        CandidateBlocked(
                            run_id=run_id,
                            source="pipeline",
                            symbol=symbol,
                            reason=f"stale_data_{age_days}d",
                            gate="freshness",
                        )
                    )
                    continue

            ctx = DecisionContext(obs, symbol)

            cand = _evaluate_candidate(
                symbol,
                ctx,
                run_date,
                regime,
                gate_threshold,
                blackout_schedule=blackout_schedule,
            )
            if cand is None:
                continue

            if cand.block_reason is not None:
                events.append(
                    CandidateBlocked(
                        run_id=run_id,
                        source="pipeline",
                        symbol=symbol,
                        reason=cand.block_reason,
                        gate="ranking"
                        if cand.block_reason == "composite_below_threshold"
                        else "mechanism",
                    )
                )
                continue

            candidates.append(cand)
            events.append(
                CandidateScored(
                    run_id=run_id,
                    source="pipeline",
                    symbol=symbol,
                    composite_score=cand.composite_score,
                    components=dict(cand.scores),
                )
            )

        current_positions = [p for p in store.load_positions() if p.quantity > 0]
        sector_map: dict[str, str] = {}
        ranked = rank_candidates(
            candidates, cfg.max_positions, len(current_positions), sector_map=sector_map
        )

        for cand in ranked[:slots]:
            ctx = DecisionContext(obs, cand.symbol)
            close = ctx.latest_close()
            if close is None:
                continue

            d_atr = _dollar_atr(obs, cand.symbol)

            pop_equity = (prev_equity or 100_000.0) + cash_adjust
            sized = size_position(pop_equity, close, d_atr, effective_mult, 1.0, sc)
            if sized.shares <= 0:
                continue
            final_shares = sized.shares

            prev_bar = None
            so = obs.per_symbol.get(cand.symbol)
            if so:
                for b in so.bars:
                    if b.effective_date < run_date:
                        prev_bar = b
            prev_close_val = prev_bar.close if prev_bar else 0.0

            order = Order(
                order_id=f"{cand.symbol}_{uuid.uuid4().hex[:8]}",
                symbol=cand.symbol,
                action="buy",
                quantity=float(final_shares),
                order_type="market",
                status="submitted",
                submitted_at=datetime.combine(run_date, datetime.min.time()),
            )

            bar_obs = _bar_for_date(obs, cand.symbol, run_date)
            if bar_obs is None:
                continue
            bar = _make_bar(bar_obs, cand.symbol)

            fill = fill_entry_order(order, bar, prev_close_val, config=fc)
            if fill is None:
                events.append(
                    CandidateBlocked(
                        run_id=run_id,
                        source="pipeline",
                        symbol=cand.symbol,
                        gate="fill",
                        reason=(
                            f"Entry blocked: gap-through or fill failure"
                            f" (gap > {fc.max_gap_pct:.1%})"
                        ),
                    )
                )
                events.append(
                    ErrorOccurred(
                        run_id=run_id,
                        source="pipeline",
                        error=f"fill_entry_order returned None for {cand.symbol}",
                        context={"symbol": cand.symbol, "operation": "fill_entry_order"},
                    )
                )
                continue

            cost = round(fill.quantity * fill.price, 2)
            entry_cost += cost

            decision_id = uuid.uuid4().hex[:16]
            stop_price = round(close - rc.stop_atr_mult * d_atr, 2)

            pos = Position(
                symbol=cand.symbol,
                quantity=float(fill.quantity),
                entry_price=fill.price,
                avg_cost=fill.price,
                current_price=fill.price,
                stop_price=stop_price,
                market_value=cost,
                decision_id=decision_id,
                entry_date=run_date,
                high_since_entry=bar.high,
            )
            store.save_position(pos)

            entry_decisions.append(
                Decision(
                    decision_id=decision_id,
                    symbol=cand.symbol,
                    date=run_date,
                    action="enter",
                    confidence=cand.composite_score,
                    reasons=["composite_score"],
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

    initial_cash = prev_equity or 100_000.0
    prev_snap = store.load_latest_portfolio_snapshot()
    if prev_snap is not None:
        today_cash = prev_snap.cash + cash_adjust - entry_cost
    else:
        today_cash = initial_cash + cash_adjust - entry_cost
    all_positions = store.load_positions()
    today_market_value = sum(
        max(prices.get(pos.symbol, pos.current_price or 0.0), 0.0) * max(pos.quantity, 0)
        for pos in all_positions
    )
    today_equity = today_cash + today_market_value

    if prev_snap is not None:
        today_pnl = today_equity - prev_snap.equity
        daily_halt_actions = evaluate_daily_loss(today_pnl, prev_snap.equity, rc)
        for action in daily_halt_actions:
            events.append(action)  # type: ignore  # RiskAction ≠ DomainEvent; stored as JSON payload

    main_snap = PortfolioSnapshot(
        date=run_date, cash=today_cash, equity=today_equity, regime=regime
    )
    store.save_portfolio_snapshot(main_snap)

    events.append(
        PipelineStepCompleted(
            run_id=run_id,
            source="pipeline",
            step_name="decide",
            duration_s=(datetime.now(UTC) - _ts_decide).total_seconds(),
            items_processed=len(entry_decisions),
        )
    )

    with _time_step("mark_to_market", run_id, events, symbols_processed=len(all_positions)):
        for pos in all_positions:
            price = prices.get(pos.symbol)
            if price is not None and pos.quantity > 0:
                mark = round(pos.quantity * price, 2)
                unrel_pl = round((price - pos.avg_cost) * pos.quantity, 2)
                store.save_position(
                    pos.model_copy(
                        update={
                            "current_price": price,
                            "market_value": mark,
                            "unrealized_pl": unrel_pl,
                        }
                    )
                )

    with _time_step("consistency", run_id, events):
        prev_snap_sc = store.load_latest_portfolio_snapshot()
        base = prev_snap_sc.cash if prev_snap_sc else (prev_equity or 0.0)
        cash = base + cash_adjust - entry_cost
        all_positions = store.load_positions()
        total_mark = sum(p.market_value or 0 for p in all_positions)
        current_equity = round(cash + total_mark, 2)
        inv = check_invariants(equity=current_equity, cash=cash, positions=all_positions)
        violations.extend(inv)

    for v in violations:
        events.append(
            ConsistencyViolation(run_id=run_id, source="pipeline", check=v.check, detail=v.detail)
        )

    pop_equity_final = current_equity
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


def persist_run_result(store: Store, result: RunResult) -> None:
    for event in result.events:
        try:
            store.save_event(event)
        except Exception:
            logger.exception("persist_event_failed", run_id=result.run_id)
    for decision in result.decisions:
        try:
            store.save_decision(decision)
        except Exception:
            logger.exception("persist_decision_failed", run_id=result.run_id)
    for fill in result.fills:
        try:
            store.save_fill(fill)
        except Exception:
            logger.exception("persist_fill_failed", run_id=result.run_id)

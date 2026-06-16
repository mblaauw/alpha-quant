from __future__ import annotations

import uuid
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime

import structlog

from alpha_quant.app._loop import (
    MechanismData,
    compute_atr,
    decide_candidates,
    detect_regime_and_multiplier,
    ensure_spy,
    evaluate_risk_actions,
    get_bar_for_date,
    size_entry,
)
from alpha_quant.app.halt import write_halt
from alpha_quant.domain.ablation import (
    AblationConfig,
    ShadowBook,
)
from alpha_quant.domain.degradation import DegradationStatus, m3_threshold_multiplier
from alpha_quant.domain.derive import backfill_indicator_state
from alpha_quant.domain.events import (
    CandidateBlocked,
    CandidatePromoted,
    CandidateScored,
    ConsistencyViolation,
    DataIngested,
    DataQuarantined,
    DomainEvent,
    DrawdownLadderTripped,
    ErrorOccurred,
    FillBooked,
    IndicatorStateUpdated,
    PartialTaken,
    PipelineRunCompleted,
    PipelineRunStarted,
    PipelineStepCompleted,
    RegimeChanged,
    SourceDegraded,
    StalenessHaltSet,
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
from alpha_quant.domain.ranking import rank as rank_candidates
from alpha_quant.domain.risk import (
    RiskConfig,
    evaluate_daily_loss,
    evaluate_drawdown,
)
from alpha_quant.domain.sizing import SizingConfig
from alpha_quant.domain.validate import validate_bars, validate_indicator_state
from alpha_quant.ports.market_data import MarketData
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
    events: list[DomainEvent]
    violations: list[InvariantViolation]
    current_regime: str | None = None
    halted: bool = False
    prev_equity: float | None = None
    new_equity: float | None = None


@contextmanager
def _time_step(
    step_name: str,
    run_id: str,
    events: list[DomainEvent],
    symbols_processed: int = 0,
    items_processed: int = 0,
) -> Generator[None]:
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


def run(
    run_date: date,
    store: Store,
    universe: list[str],
    config: PipelineConfig | None = None,
    fill_config: FillConfig | None = None,
    risk_config: RiskConfig | None = None,
    sizing_config: SizingConfig | None = None,
    market_data: MarketData | None = None,
    prev_equity: float | None = None,
    prev_regime: str = "CAUTION",
    degradation: DegradationStatus | None = None,
    shadow_books: dict[str, ShadowBook] | None = None,
) -> RunResult:
    cfg = config or PipelineConfig()
    fc = fill_config or FillConfig()
    rc = risk_config or RiskConfig()
    sc = sizing_config or SizingConfig()
    deg = degradation or DegradationStatus()

    run_id = cfg.run_id or uuid.uuid4().hex[:16]
    events: list[DomainEvent] = []
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
    with _time_step("bar_load", run_id, events, symbols_processed=len(symbols)):
        for symbol in symbols:
            bars: list[Bar] = []
            try:
                bars = store.load_bars(symbol, lookback_start, run_date)
            except Exception:
                logger.warning("store_bar_load_failed", symbol=symbol)
            if not bars and market_data is not None:
                try:
                    bars = market_data.daily_bars(symbol, lookback_start, run_date)
                    if bars:
                        events.append(
                            DataIngested(
                                run_id=run_id,
                                source="pipeline",
                                connector="market_data",
                                symbol=symbol,
                                records=len(bars),
                            )
                        )
                except Exception:
                    logger.exception("market_data_bar_load_failed", symbol=symbol)
            if bars:
                all_bars[symbol] = bars
            else:
                events.append(
                    SourceDegraded(
                        run_id=run_id,
                        source="pipeline",
                        source_name=symbol,
                        fallback="skip",
                    )
                )
                events.append(
                    ErrorOccurred(
                        run_id=run_id,
                        source="pipeline",
                        error="No bar data from store or market_data",
                        context={"symbol": symbol, "operation": "bar_load"},
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
    with _time_step("validate", run_id, events, symbols_processed=len(all_bars)):
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
                    events.append(
                        StalenessHaltSet(
                            run_id=run_id,
                            source="pipeline",
                            symbol=symbol,
                            hours_since_last=0.0,
                        )
                    )

    # --- 3. Derive indicators ---
    indicator_states: dict[str, IndicatorState] = {}
    with _time_step("derive", run_id, events, symbols_processed=len(all_bars)):
        for symbol, bars in all_bars.items():
            if bars:
                try:
                    indicator_states[symbol] = backfill_indicator_state(bars)
                    events.append(
                        IndicatorStateUpdated(
                            run_id=run_id,
                            source="pipeline",
                            symbol=symbol,
                            indicator_count=len(bars),
                        )
                    )
                except Exception as e:
                    logger.exception("indicator_backfill_failed", symbol=symbol)
                    events.append(
                        ErrorOccurred(
                            run_id=run_id,
                            source="pipeline",
                            error=str(e),
                            context={"symbol": symbol, "operation": "indicator_backfill"},
                        )
                    )

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
    with _time_step("regime", run_id, events):
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
    _ts_risk = datetime.now(UTC)
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
        risk_actions = evaluate_risk_actions(pos, bar, state, rc, run_date)

        for action in risk_actions:
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
            events.append(
                FillBooked(
                    run_id=run_id,
                    source="pipeline",
                    fill=exit_fill,
                )
            )
            if action.action_type == "time_stop":
                entry_date = pos.entry_date or run_date
                events.append(
                    TimeStopTriggered(
                        run_id=run_id,
                        source="pipeline",
                        symbol=sym,
                        days_held=(run_date - entry_date).days,
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

    # --- 5b. Portfolio-level risk (drawdown) ---
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

    # --- 6. Decide (score + rank + size) ---
    _ts_decide = datetime.now(UTC)
    new_positions_count = len([p for p in store.load_positions() if p.quantity > 0])
    slots = cfg.max_positions - new_positions_count

    # Load mechanism data (needed for main book and shadow books)
    mech_data = MechanismData()
    for symbol in universe:
        try:
            fund = store.load_fundamentals(symbol)
            if fund:
                mech_data.fundamentals[symbol] = fund[0]
        except Exception:
            pass
        try:
            txns = store.load_insider_transactions(symbol)
            if txns:
                mech_data.insider_txns[symbol] = txns
        except Exception:
            pass
        try:
            earnings = store.load_earnings(symbol)
            if earnings:
                mech_data.earnings[symbol] = earnings
        except Exception:
            pass
        try:
            mentions = store.load_mentions(symbol)
            if mentions:
                mech_data.mentions[symbol] = mentions
        except Exception:
            pass

    gate_threshold = 0.5 * m3_threshold_multiplier(deg)

    entry_decisions: list[Decision] = []
    effective_mult = regime_mult * dd_verdict.multiplier
    entry_cost: float = 0.0
    sector_map = {
        sym: snap.sector
        for sym, snap in mech_data.fundamentals.items()
        if snap is not None and snap.sector is not None
    }
    if slots > 0 and effective_mult > 0:
        all_considered = decide_candidates(
            universe,
            all_bars,
            indicator_states,
            run_date,
            regime,
            mech_data,
            ablation=cfg.ablation,
        )

        candidates: list[Candidate] = []
        for cand in all_considered:
            if cand.block_reason is not None:
                events.append(
                    CandidateBlocked(
                        run_id=run_id,
                        source="pipeline",
                        symbol=cand.symbol,
                        reason=cand.block_reason,
                        gate="mechanism",
                    )
                )
                continue

            if cand.composite_score < gate_threshold:
                events.append(
                    CandidateBlocked(
                        run_id=run_id,
                        source="pipeline",
                        symbol=cand.symbol,
                        reason="composite_below_threshold",
                        gate="ranking",
                    )
                )
                continue

            candidates.append(cand)
            events.append(
                CandidateScored(
                    run_id=run_id,
                    source="pipeline",
                    symbol=cand.symbol,
                    composite_score=cand.composite_score,
                    components=dict(cand.scores),
                )
            )

        current_positions = [p for p in store.load_positions() if p.quantity > 0]
        ranked = rank_candidates(
            candidates,
            cfg.max_positions,
            len(current_positions),
            sector_map=sector_map,
        )

        for cand in ranked[:slots]:
            bar = get_bar_for_date(all_bars, cand.symbol, run_date)
            state = indicator_states.get(cand.symbol)
            if bar is None or state is None:
                continue
            atr_val = compute_atr(state, bar.close)

            pop_equity = (prev_equity or 100_000.0) + cash_adjust
            sized = size_entry(pop_equity, bar.close, atr_val, effective_mult, sc)
            if sized is None:
                continue
            final_shares = sized.shares

            bars_for_symbol = all_bars.get(cand.symbol, [])
            bars_to_date = [b for b in bars_for_symbol if b.date < run_date]
            prev_close = bars_to_date[-1].close if bars_to_date else 0.0
            order = Order(
                order_id=f"{cand.symbol}_{uuid.uuid4().hex[:8]}",
                symbol=cand.symbol,
                action="buy",
                quantity=float(final_shares),
                order_type="MARKET",
                status="submitted",
                submitted_at=run_date,
            )
            fill = fill_entry_order(order, bar, prev_close, config=fc)
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
            stop_price = round(bar.close - rc.stop_atr_mult * atr_val, 2)

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

    # --- 6b. Daily loss check ---
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
        daily_halt_actions = evaluate_daily_loss(today_pnl, today_equity, rc)
        for action in daily_halt_actions:
            events.append(action)  # type: ignore

    main_snap = PortfolioSnapshot(
        date=run_date,
        cash=today_cash,
        equity=today_equity,
        regime=regime,
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

    # --- 7. Shadow books ---
    _ts_shadow = datetime.now(UTC)
    if shadow_books is not None:
        pop_equity = (prev_equity or 100_000.0) + cash_adjust
        if mech_data is None:
            mech_data = MechanismData()

        for shadow_name, shadow_book in shadow_books.items():
            sh_config = shadow_book._config
            sh_results_fills: list[Fill] = []

            # Skip if no slots (no new entries possible)
            sh_has_cash = slots > 0 and regime_mult > 0

            if sh_has_cash:
                sh_considered = decide_candidates(
                    universe,
                    all_bars,
                    indicator_states,
                    run_date,
                    regime,
                    mech_data,
                    ablation=sh_config,
                )
                sh_candidates: list[Candidate] = []
                for cand in sh_considered:
                    if cand.block_reason is not None:
                        continue
                    if cand.composite_score < gate_threshold:
                        continue
                    sh_candidates.append(cand)

                sh_current = len(shadow_book.positions)
                sh_ranked = rank_candidates(
                    sh_candidates,
                    cfg.max_positions,
                    sh_current,
                    sector_map=sector_map,
                )

                sh_orders: list[Order] = []
                for cand in sh_ranked[:slots]:
                    bar = get_bar_for_date(all_bars, cand.symbol, run_date)
                    state = indicator_states.get(cand.symbol)
                    if bar is None or state is None:
                        continue
                    atr_val = compute_atr(state, bar.close)
                    sized = size_entry(pop_equity, bar.close, atr_val, effective_mult, sc)
                    if sized is None:
                        continue
                    sh_orders.append(
                        Order(
                            order_id=f"{shadow_name}_{cand.symbol}_{uuid.uuid4().hex[:8]}",
                            symbol=cand.symbol,
                            action="buy",
                            quantity=int(sized.shares),
                            order_type="MARKET",
                            status="submitted",
                            submitted_at=datetime.now(UTC),
                        )
                    )

                # Process entries
                if sh_orders:
                    first_sym = universe[0] if universe else "SPY"
                    entry_bar = get_bar_for_date(all_bars, first_sym, run_date)
                    if entry_bar is not None:
                        prev_close = prices.get("SPY", entry_bar.close)
                        fill_res = shadow_book.process_entry_orders(
                            sh_orders,
                            entry_bar,
                            prev_close,
                            fill_config=fc,
                        )
                        sh_results_fills.extend(fill_res.fills)
                        violations.extend(fill_res.violations)

            # Process risk actions for shadow positions
            for shadow_pos in shadow_book.positions:
                bar = get_bar_for_date(all_bars, shadow_pos.symbol, run_date)
                if bar is None:
                    continue
                state = indicator_states.get(shadow_pos.symbol)
                sh_risk_actions = evaluate_risk_actions(shadow_pos, bar, state, rc, run_date)
                risk_res = shadow_book.process_risk_actions(sh_risk_actions, bar)
                sh_results_fills.extend(risk_res.fills)
                violations.extend(risk_res.violations)

            # Mark to market and persist snapshot
            prev_sh_snap = store.load_latest_portfolio_snapshot(book=shadow_name)
            prev_sh_equity = prev_sh_snap.equity if prev_sh_snap else None
            sh_snap = shadow_book.mark_to_market(run_date, prices, prev_sh_equity)
            store.save_portfolio_snapshot(sh_snap)

            fills.extend(sh_results_fills)

    events.append(
        PipelineStepCompleted(
            run_id=run_id,
            source="pipeline",
            step_name="shadow_books",
            duration_s=(datetime.now(UTC) - _ts_shadow).total_seconds(),
            items_processed=len(shadow_books) if shadow_books else 0,
        )
    )

    # --- Mark to market ---
    with _time_step("mark_to_market", run_id, events, symbols_processed=len(all_positions)):
        all_positions = store.load_positions()
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

    # --- Self-consistency ---
    with _time_step("consistency", run_id, events):
        prev_snap_sc = store.load_latest_portfolio_snapshot()
        base = prev_snap_sc.cash if prev_snap_sc else (prev_equity or 0.0)
        cash = base + cash_adjust - entry_cost
        all_positions = store.load_positions()
        total_mark = sum(p.market_value or 0 for p in all_positions)
        current_equity = round(cash + total_mark, 2)
        inv = check_invariants(equity=current_equity, cash=cash, positions=all_positions)
        violations.extend(inv)
    for v in inv:
        events.append(
            ConsistencyViolation(
                run_id=run_id,
                source="pipeline",
                check=v.check,
                detail=v.detail,
            )
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

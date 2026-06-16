from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import structlog

from alpha_quant.app._loop import (
    MechanismData,
    compute_atr,
    decide_candidates,
    detect_regime_and_multiplier,
    ensure_spy,
    evaluate_risk_actions,
    get_date_bars,
    load_all_bars,
    size_entry,
)
from alpha_quant.domain.ablation import AblationConfig, compute_spy_buy_and_hold
from alpha_quant.domain.constants import LOOKBACK_DAYS
from alpha_quant.domain.derive import backfill_indicator_state, update_indicator_state
from alpha_quant.domain.fills import FillConfig, fill_entry_order, fill_stop_loss
from alpha_quant.domain.models import (
    Decision,
    Fill,
    IndicatorState,
    Order,
    Position,
)
from alpha_quant.domain.ranking import rank as rank_candidates
from alpha_quant.domain.risk import (
    RiskConfig,
    evaluate_daily_loss,
    evaluate_drawdown,
)
from alpha_quant.domain.sizing import SizingConfig
from alpha_quant.ports.store import Store

logger = structlog.get_logger()


@dataclass
class BacktestConfig:
    start_date: date
    end_date: date
    symbols: list[str]
    initial_equity: float = 100_000.0
    max_positions: int = 10
    ablation: AblationConfig | None = None


@dataclass
class BacktestMetrics:
    total_return_pct: float = 0.0
    cagr: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe: float = 0.0
    sortino: float = 0.0
    num_trades: int = 0
    win_rate: float = 0.0
    avg_hold_days: float = 0.0
    spy_return_pct: float | None = None
    spy_cagr: float | None = None
    spy_max_dd_pct: float | None = None
    spy_sharpe: float | None = None


@dataclass
class BacktestStep:
    date: date
    equity: float
    cash: float
    num_positions: int


@dataclass
class BacktestResult:
    config: BacktestConfig
    steps: list[BacktestStep] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    metrics: BacktestMetrics = field(default_factory=BacktestMetrics)


def _compute_metrics(
    equity_curve: list[float],
    returns: list[float],
    num_trades: int,
    win_rate: float,
    avg_hold_days: float,
    spy_curve: list[float] | None = None,
    spy_returns: list[float] | None = None,
) -> BacktestMetrics:
    if len(equity_curve) < 2:
        return BacktestMetrics()

    initial, final = equity_curve[0], equity_curve[-1]
    total_return = (final - initial) / initial
    daily_returns = np.array(returns)
    years = len(equity_curve) / 252.0 if len(equity_curve) > 0 else 1.0
    cagr = (1.0 + total_return) ** (1.0 / years) - 1.0

    peak = np.maximum.accumulate(equity_curve)
    dd = (equity_curve - peak) / peak
    max_dd = float(np.min(dd))

    if len(daily_returns) < 2 or np.std(daily_returns) < 1e-10:
        return BacktestMetrics(
            total_return_pct=round(total_return * 100, 2),
            cagr=round(cagr * 100, 2),
            max_drawdown_pct=round(max_dd * 100, 2),
            num_trades=num_trades,
            win_rate=round(win_rate * 100, 1),
            avg_hold_days=round(avg_hold_days, 1),
        )

    af = np.sqrt(252.0)
    sharpe = float(np.mean(daily_returns) / np.std(daily_returns) * af)
    downside = daily_returns[daily_returns < 0]
    down_std = np.std(downside) if len(downside) > 0 else np.std(daily_returns)
    sortino = float(np.mean(daily_returns) / down_std * af)

    spy_r = spy_c = spy_d = spy_sh = None
    if spy_curve and len(spy_curve) >= 2:
        spy_initial, spy_final = spy_curve[0], spy_curve[-1]
        spy_r = round((spy_final - spy_initial) / spy_initial * 100, 2)
        spy_years = len(spy_curve) / 252.0
        spy_c = (
            round(
                ((1.0 + (spy_final - spy_initial) / spy_initial) ** (1.0 / spy_years) - 1.0) * 100,
                2,
            )
            if spy_years > 0
            else 0.0
        )  # noqa: E501
        spy_peak = np.maximum.accumulate(spy_curve)
        spy_dd = (spy_curve - spy_peak) / spy_peak
        spy_d = round(float(np.min(spy_dd)) * 100, 2)
        if spy_returns and len(spy_returns) >= 2 and np.std(spy_returns) >= 1e-10:
            spy_sh = round(float(np.mean(spy_returns) / np.std(spy_returns) * np.sqrt(252.0)), 3)

    return BacktestMetrics(
        total_return_pct=round(total_return * 100, 2),
        cagr=round(cagr * 100, 2),
        max_drawdown_pct=round(max_dd * 100, 2),
        sharpe=round(sharpe, 3),
        sortino=round(sortino, 3),
        num_trades=num_trades,
        win_rate=round(win_rate * 100, 1),
        avg_hold_days=round(avg_hold_days, 1),
        spy_return_pct=spy_r,
        spy_cagr=spy_c,
        spy_max_dd_pct=spy_d,
        spy_sharpe=spy_sh,
    )


def _trading_dates(store: Store, start: date, end: date) -> list[date]:
    bars = store.load_bars("SPY", start, end)
    seen: set[date] = set()
    result: list[date] = []
    for b in bars:
        if b.date not in seen and start <= b.date <= end:
            seen.add(b.date)
            result.append(b.date)
    return result


def run_backtest(
    config: BacktestConfig,
    store: Store,
    fill_config: FillConfig | None = None,
    risk_config: RiskConfig | None = None,
    sizing_config: SizingConfig | None = None,
) -> BacktestResult:
    rc = risk_config or RiskConfig()
    sc = sizing_config or SizingConfig()

    lookback_start = date.fromordinal(config.start_date.toordinal() - LOOKBACK_DAYS)
    symbols = ensure_spy(config.symbols)
    all_bars = load_all_bars(store, symbols, lookback_start, config.end_date)

    mech_data = MechanismData()
    for symbol in config.symbols:
        try:
            fund = store.load_fundamentals(symbol)
            if fund:
                mech_data.fundamentals[symbol] = fund[0]
        except Exception:
            logger.warning("Failed to load fundamentals", symbol=symbol)
        try:
            txns = store.load_insider_transactions(symbol)
            if txns:
                mech_data.insider_txns[symbol] = txns
        except Exception:
            logger.warning("Failed to load insider_txns", symbol=symbol)
        try:
            earnings = store.load_earnings(symbol)
            if earnings:
                mech_data.earnings[symbol] = earnings
        except Exception:
            logger.warning("Failed to load earnings", symbol=symbol)
        try:
            mentions = store.load_mentions(symbol)
            if mentions:
                mech_data.mentions[symbol] = mentions
        except Exception:
            logger.warning("Failed to load mentions", symbol=symbol)

    trading_dates = _trading_dates(store, config.start_date, config.end_date)
    if not trading_dates or not all_bars.get("SPY"):
        return BacktestResult(config=config)

    indicator_states: dict[str, IndicatorState] = {}

    cash: float = config.initial_equity
    positions: dict[str, Position] = {}
    steps: list[BacktestStep] = []
    decisions: list[Decision] = []
    all_fills: list[Fill] = []
    equity_curve: list[float] = []
    daily_returns: list[float] = []
    prev_equity: float | None = None
    last_close: dict[str, float] = {}

    trade_count: int = 0
    win_count: int = 0
    hold_days_total: int = 0
    hold_trade_count: int = 0
    entry_dates: dict[str, date] = {}

    for trade_date in trading_dates:
        date_bars = get_date_bars(all_bars, trade_date)

        spy_bar = date_bars.get("SPY")
        if spy_bar is None:
            continue

        for symbol, bar in date_bars.items():
            prev = indicator_states.get(symbol)
            if prev is None:
                prev_bars = [b for b in all_bars.get(symbol, []) if b.date < trade_date]
                bootstrap = prev_bars + [bar]
                indicator_states[symbol] = backfill_indicator_state(bootstrap)
            else:
                indicator_states[symbol] = update_indicator_state(prev, bar)

        prices: dict[str, float] = {s: b.close for s, b in date_bars.items()}

        # --- Risk exits ---
        for sym in list(positions.keys()):
            pos = positions[sym]
            if pos.quantity <= 0:
                continue
            bar = date_bars.get(sym)
            if bar is None:
                continue
            state = indicator_states.get(sym)
            risk_actions = evaluate_risk_actions(
                pos,
                bar,
                state,
                rc,
                trade_date,
            )

            new_high = max(pos.high_since_entry or pos.entry_price or 0.0, bar.high)
            if new_high > (pos.high_since_entry or 0.0):
                pos = pos.model_copy(update={"high_since_entry": new_high})
                positions[sym] = pos

            if risk_actions:
                fill = fill_stop_loss(pos, bar, order_id=f"{sym}_stop", config=fill_config)
                if fill is None:
                    continue
                sell_price = fill.price
                qty = abs(fill.quantity)
                proceeds = round(qty * sell_price, 2)
                pl = round((sell_price - pos.avg_cost) * qty, 2)
                cash += proceeds
                all_fills.append(fill)
                trade_count += 1
                if pl > 0:
                    win_count += 1
                held = (trade_date - entry_dates.get(sym, trade_date)).days
                hold_days_total += held
                hold_trade_count += 1
                entry_dates.pop(sym, None)
                positions.pop(sym, None)

        # --- Portfolio-level risk (drawdown) ---
        dd_verdict = evaluate_drawdown(equity_curve, rc)
        dd_mult = dd_verdict.multiplier

        # --- Entries ---
        if len(positions) < config.max_positions and dd_mult > 0:
            spy_state = indicator_states.get("SPY")
            regime, regime_mult = detect_regime_and_multiplier(spy_state)

            all_considered = decide_candidates(
                config.symbols,
                all_bars,
                indicator_states,
                trade_date,
                regime,
                mech_data,
                ablation=config.ablation,
            )
            candidates = [c for c in all_considered if c.block_reason is None]

            current_positions = list(positions.values())
            sector_map = {
                sym: snap.sector
                for sym, snap in mech_data.fundamentals.items()
                if snap is not None and snap.sector is not None
            }
            ranked = rank_candidates(
                candidates,
                config.max_positions,
                len(current_positions),
                sector_map=sector_map,
            )
            slots = config.max_positions - len(positions)

            for cand in ranked[:slots]:
                bar = date_bars.get(cand.symbol)
                state = indicator_states.get(cand.symbol)
                if bar is None or state is None:
                    continue
                prev_close = last_close.get(cand.symbol, 0.0)
                atr_val = compute_atr(state, bar.close)

                total_equity = cash + sum(
                    p.quantity * prices.get(p.symbol, 0.0) for p in positions.values()
                )

                sized = size_entry(total_equity, bar.close, atr_val, regime_mult * dd_mult, sc)
                if sized is None:
                    continue
                final_shares = sized.shares

                order_id = uuid.uuid4().hex[:16]
                order = Order(
                    order_id=order_id,
                    symbol=cand.symbol,
                    action="buy",
                    quantity=float(final_shares),
                    order_type="market",
                    status="submitted",
                )
                fill = fill_entry_order(order, bar, prev_close, config=fill_config)
                if fill is None:
                    continue
                fill_price = fill.price
                cost = round(float(final_shares) * fill_price, 2)
                if cost > cash:
                    continue

                cash -= cost
                all_fills.append(fill)
                stop_price = round(fill_price - rc.stop_atr_mult * atr_val, 2)

                pos = Position(
                    symbol=cand.symbol,
                    quantity=float(final_shares),
                    entry_price=fill_price,
                    avg_cost=fill_price,
                    current_price=fill_price,
                    stop_price=stop_price,
                    market_value=cost,
                    decision_id=uuid.uuid4().hex[:16],
                    entry_date=trade_date,
                    high_since_entry=bar.high,
                )
                positions[cand.symbol] = pos

        # --- Mark to market ---
        total_mark = 0.0
        for sym, pos in positions.items():
            price = prices.get(sym)
            if price is not None:
                mv = round(pos.quantity * price, 2)
                total_mark += mv
                positions[sym] = pos.model_copy(update={"current_price": price, "market_value": mv})

        equity = round(cash + total_mark, 2)
        if prev_equity is not None and prev_equity > 0:
            daily_returns.append((equity - prev_equity) / prev_equity)
            today_pnl = equity - prev_equity
            # Daily halt is informational in backtest; doesn't prevent entries
            evaluate_daily_loss(today_pnl, equity, rc)
        prev_equity = equity
        equity_curve.append(equity)

        for symbol, bar in date_bars.items():
            last_close[symbol] = bar.close

        steps.append(
            BacktestStep(
                date=trade_date,
                equity=equity,
                cash=cash,
                num_positions=len(positions),
            )
        )

    win_rate = win_count / trade_count if trade_count > 0 else 0.0
    avg_hold = hold_days_total / hold_trade_count if hold_trade_count > 0 else 0.0

    spy_curve = compute_spy_buy_and_hold(
        all_bars.get("SPY", []), config.start_date, config.end_date, config.initial_equity
    )  # noqa: E501
    spy_returns = []
    for i in range(1, len(spy_curve)):
        if spy_curve[i - 1] > 0:
            spy_returns.append((spy_curve[i] - spy_curve[i - 1]) / spy_curve[i - 1])

    metrics = _compute_metrics(
        equity_curve, daily_returns, trade_count, win_rate, avg_hold, spy_curve, spy_returns
    )  # noqa: E501

    return BacktestResult(
        config=config,
        steps=steps,
        decisions=decisions,
        fills=all_fills,
        metrics=metrics,
    )

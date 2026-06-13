from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

import numpy as np

from alpha_quant.app._loop import (
    bars_up_to,
    compute_atr,
    detect_regime_and_multiplier,
    ensure_spy,
    evaluate_risk_actions,
    get_date_bars,
    load_all_bars,
    score_candidate,
    size_entry,
)
from alpha_quant.domain.ablation import compute_spy_buy_and_hold
from alpha_quant.domain.derive import backfill_indicator_state, update_indicator_state
from alpha_quant.domain.fills import FillConfig, fill_entry_order, fill_stop_loss
from alpha_quant.domain.models import (
    Candidate,
    Decision,
    Fill,
    IndicatorState,
    Order,
    Position,
)
from alpha_quant.domain.ranking import rank as rank_candidates
from alpha_quant.domain.risk import RiskConfig
from alpha_quant.domain.sizing import SizingConfig
from alpha_quant.ports.store import Store

_LOOKBACK_DAYS = 400


@dataclass
class BacktestConfig:
    start_date: date
    end_date: date
    symbols: list[str]
    initial_equity: float = 100_000.0
    max_positions: int = 10


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

    lookback_start = date.fromordinal(config.start_date.toordinal() - _LOOKBACK_DAYS)
    symbols = ensure_spy(config.symbols)
    all_bars = load_all_bars(store, symbols, lookback_start, config.end_date)

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
                entry_dates.get(sym, trade_date),
                trade_date,
            )

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

        # --- Entries ---
        if len(positions) < config.max_positions:
            spy_state = indicator_states.get("SPY")
            regime, regime_mult = detect_regime_and_multiplier(spy_state)

            candidates: list[Candidate] = []
            for symbol in config.symbols:
                bar = date_bars.get(symbol)
                state = indicator_states.get(symbol)
                if bar is None or state is None:
                    continue
                if np.isnan(state.values.get("rsi", np.nan)):
                    continue

                bars_to_date = bars_up_to(all_bars, symbol, trade_date)
                candidates.append(
                    score_candidate(symbol, bars_to_date, bar, state, trade_date, regime),
                )

            current_positions = list(positions.values())
            ranked = rank_candidates(candidates, config.max_positions, len(current_positions))
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

                sized = size_entry(total_equity, bar.close, atr_val, regime_mult, sc)
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
                )
                positions[cand.symbol] = pos
                entry_dates[cand.symbol] = trade_date

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

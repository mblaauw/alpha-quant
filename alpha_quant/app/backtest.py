from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

import numpy as np

from alpha_quant.domain.derive import backfill_indicator_state, update_indicator_state
from alpha_quant.domain.fills import FillConfig
from alpha_quant.domain.models import Bar, Candidate, Decision, Fill, IndicatorState, Position
from alpha_quant.domain.ranking import rank as rank_candidates
from alpha_quant.domain.regime import detect as detect_regime
from alpha_quant.domain.risk import RiskConfig, evaluate_stops, evaluate_time_stop
from alpha_quant.domain.sizing import SizingConfig, size_position
from alpha_quant.domain.technical import score as score_technical
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

    return BacktestMetrics(
        total_return_pct=round(total_return * 100, 2),
        cagr=round(cagr * 100, 2),
        max_drawdown_pct=round(max_dd * 100, 2),
        sharpe=round(sharpe, 3),
        sortino=round(sortino, 3),
        num_trades=num_trades,
        win_rate=round(win_rate * 100, 1),
        avg_hold_days=round(avg_hold_days, 1),
    )


def _momentum_score(bars: list[Bar], close: float) -> float:
    n = len(bars)
    if n < 2:
        return 0.3
    lookback = min(63, n - 1)
    prev_close = bars[-(lookback + 1)].close
    if prev_close <= 0:
        return 0.0
    ret = (close - prev_close) / prev_close
    if ret > 0.20:
        return 1.0
    if ret > 0.10:
        return 0.8
    if ret > 0.05:
        return 0.6
    if ret > 0.0:
        return 0.5
    if ret > -0.05:
        return 0.3
    if ret > -0.15:
        return 0.1
    return 0.0


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
    symbols = list(config.symbols)
    if "SPY" not in symbols:
        symbols.append("SPY")

    all_bars: dict[str, list[Bar]] = {}
    for symbol in symbols:
        bars = store.load_bars(symbol, lookback_start, config.end_date)
        if bars:
            all_bars[symbol] = bars

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

    trade_count: int = 0
    win_count: int = 0
    hold_days_total: int = 0
    hold_trade_count: int = 0
    entry_dates: dict[str, date] = {}

    for trade_date in trading_dates:
        date_bars: dict[str, Bar] = {}
        for symbol, bars in all_bars.items():
            day_bars = [b for b in bars if b.date == trade_date]
            if day_bars:
                date_bars[symbol] = day_bars[0]

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
            atr = state.values.get("atr", 0.0) if state else 0.0
            if np.isnan(atr):
                atr = 0.0
            highest = max(pos.entry_price or 0.0, bar.high)

            risk_actions = evaluate_stops(pos, bar, atr, highest, rc)
            risk_actions.extend(
                evaluate_time_stop(pos, entry_dates.get(sym, trade_date), trade_date, rc)
            )

            if risk_actions:
                sell_price = max(bar.open * 0.99, bar.low)
                proceeds = round(pos.quantity * sell_price, 2)
                pl = round((sell_price - pos.avg_cost) * pos.quantity, 2)
                cash += proceeds
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
            if spy_state is not None:
                regime = detect_regime(
                    spy_state,
                    vix_level=15.0,
                    breadth=0.6,
                )
            else:
                regime = "CAUTION"
            regime_map = {"RISK_ON": 1.0, "CAUTION": 0.5, "RISK_OFF": 0.0}
            regime_mult = regime_map.get(regime, 0.5)

            candidates: list[Candidate] = []
            for symbol in config.symbols:
                bar = date_bars.get(symbol)
                state = indicator_states.get(symbol)
                if bar is None or state is None:
                    continue
                price = bar.close
                vals = state.values
                if np.isnan(vals.get("rsi", np.nan)):
                    continue

                bars_to_date = [b for b in all_bars.get(symbol, []) if b.date <= trade_date]
                tech = score_technical(bars_to_date, state)

                momentum_scr = _momentum_score(bars_to_date, bar.close)
                tech_scr = tech.score
                composite = 0.70 * tech_scr + 0.30 * momentum_scr

                candidates.append(
                    Candidate(
                        symbol=symbol,
                        date=trade_date,
                        scores={"technical": tech_scr, "momentum": momentum_scr},
                        composite_score=min(1.0, composite),
                        regime=regime,
                        gate_results={"fundamental": True, "blackout": True},
                    )
                )

            current_positions = list(positions.values())
            ranked = rank_candidates(candidates, config.max_positions, len(current_positions))
            slots = config.max_positions - len(positions)

            for cand in ranked[:slots]:
                bar = date_bars.get(cand.symbol)
                state = indicator_states.get(cand.symbol)
                if bar is None or state is None:
                    continue
                price = bar.close
                atr_val = state.values.get("atr", price * 0.02)
                if np.isnan(atr_val) or atr_val <= 0:
                    atr_val = price * 0.02

                total_equity = cash + sum(
                    p.quantity * prices.get(p.symbol, 0.0) for p in positions.values()
                )

                sized = size_position(total_equity, price, atr_val, regime_mult, 1.0, sc)
                final_shares = sized.shares
                if final_shares <= 0:
                    continue
                cost = round(final_shares * price, 2)
                if cost > cash:
                    final_shares = int(cash / price)
                    if final_shares <= 0:
                        continue
                    cost = round(final_shares * price, 2)

                cash -= cost
                stop_price = round(price - rc.stop_atr_mult * atr_val, 2)

                pos = Position(
                    symbol=cand.symbol,
                    quantity=float(final_shares),
                    entry_price=price,
                    avg_cost=price,
                    current_price=price,
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
    metrics = _compute_metrics(equity_curve, daily_returns, trade_count, win_rate, avg_hold)

    return BacktestResult(
        config=config,
        steps=steps,
        decisions=decisions,
        fills=all_fills,
        metrics=metrics,
    )

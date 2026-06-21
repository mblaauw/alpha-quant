import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import structlog

from adapters.fake.lake_fixture import FixtureLakeGateway
from adapters.fake.virtual_clock import VirtualClock
from adapters.real.lake_data import (
    LakeFundamentals,
    LakeInsiderFeed,
    LakeMarketData,
    LakeSentimentFeed,
)
from app._loop import (
    compute_atr,
    decide_candidates,
    detect_regime_and_multiplier,
    ensure_spy,
    evaluate_risk_actions,
    get_date_bars,
    size_entry,
)
from app.catalog import compute_manifest_hash
from app.config import AppConfig, redact_config
from domain.constants import LOOKBACK_DAYS
from domain.derive import backfill_indicator_state, update_indicator_state
from domain.fills import FillConfig, fill_entry_order, fill_partial_take, fill_stop_loss
from domain.models import (
    Bar,
    Decision,
    Fill,
    IndicatorState,
    Order,
    Position,
)
from domain.ranking import rank as rank_candidates
from domain.risk import RiskConfig
from domain.sizing import SizingConfig

logger = structlog.get_logger()


def _make_id(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()[:16]


def _trading_dates(bars: dict[str, list[Bar]], start: date, end: date) -> list[date]:
    spy_bars = bars.get("SPY", [])
    seen: set[date] = set()
    result: list[date] = []
    for b in spy_bars:
        if b.date not in seen and start <= b.date <= end:
            seen.add(b.date)
            result.append(b.date)
    return result


def run_replay(
    config: AppConfig,
    from_date: str,
    to_date: str,
    fixture_path: str | None = None,
    store: Any = None,
) -> dict[str, Any]:
    cfg_redacted = redact_config(config)
    config_hash = hashlib.sha256(json.dumps(cfg_redacted, sort_keys=True).encode()).hexdigest()[:16]

    fixture_hash = ""
    if fixture_path:
        fixture_hash = compute_manifest_hash(fixture_path)

    f_start = date.fromisoformat(from_date)
    f_end = date.fromisoformat(to_date)
    fp = Path(fixture_path) if fixture_path else Path("fixtures/v1")

    symbols = list(config.bootstrap.symbols) + list(config.bootstrap.include_benchmarks)

    # Use FixtureLakeGateway + VirtualClock for deterministic PIT replay
    lake = FixtureLakeGateway(fp)
    clock = VirtualClock(f_end)
    market_data = LakeMarketData(lake, clock)
    fundamentals = LakeFundamentals(lake, clock)
    insider_feed = LakeInsiderFeed(lake, clock)
    sentiment_feed = LakeSentimentFeed(lake, clock)

    lookback_start = date.fromordinal(f_start.toordinal() - LOOKBACK_DAYS)
    all_bars: dict[str, list[Bar]] = {}
    for sym in ensure_spy(symbols):
        try:
            bars = market_data.daily_bars(sym, lookback_start, f_end)
            if bars:
                all_bars[sym] = bars
        except Exception:
            logger.warning("Failed to load bars for replay", symbol=sym)

    fill_config = FillConfig()
    risk_config = RiskConfig()
    sizing_config = SizingConfig()

    mech_fundamentals: dict[str, Any] = {}
    mech_insider: dict[str, Any] = {}
    mech_mentions: dict[str, Any] = {}
    for sym in symbols:
        try:
            snap = fundamentals.snapshot(sym)
            if snap is not None:
                mech_fundamentals[sym] = snap
        except Exception:
            logger.warning("Failed to load fundamentals for replay", symbol=sym)
        try:
            txns = insider_feed.cluster_transactions(sym)
            if txns:
                mech_insider[sym] = txns
        except Exception:
            logger.warning("Failed to load insider_txns for replay", symbol=sym)
        try:
            mentions = sentiment_feed.mention_counts(sym, days=365)
            if mentions:
                mech_mentions[sym] = mentions
        except Exception:
            logger.warning("Failed to load mentions for replay", symbol=sym)

    from app._loop import MechanismData

    mech_data = MechanismData(
        fundamentals=mech_fundamentals,
        insider_txns=mech_insider,
        mentions=mech_mentions,
    )

    trading_dates = _trading_dates(all_bars, f_start, f_end)
    indicator_states: dict[str, IndicatorState] = {}

    cash: float = getattr(config.paper, "starting_equity", 100_000.0)
    positions: dict[str, Position] = {}
    decisions: list[Decision] = []
    all_fills: list[Fill] = []
    equity_curve: list[float] = []
    last_close: dict[str, float] = {}

    sector_map = {
        sym: snap.sector
        for sym, snap in mech_fundamentals.items()
        if snap is not None and snap.sector is not None
    }

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

        # Risk exits
        for sym in list(positions.keys()):
            pos = positions[sym]
            if pos.quantity <= 0:
                continue
            bar = date_bars.get(sym)
            if bar is None:
                continue
            state = indicator_states.get(sym)
            risk_actions = evaluate_risk_actions(pos, bar, state, risk_config, trade_date)

            new_high = max(pos.high_since_entry or pos.entry_price or 0.0, bar.high)
            if new_high > (pos.high_since_entry or 0.0):
                pos = pos.model_copy(update={"high_since_entry": new_high})
                positions[sym] = pos

            for action in risk_actions:
                if action.action_type in ("stop", "trail_stop", "time_stop"):
                    oid = f"{sym}_exit_{trade_date.isoformat()}"
                    fill = fill_stop_loss(pos, bar, order_id=oid, config=fill_config)
                    if fill is None:
                        continue
                    proceeds = round(abs(fill.quantity) * fill.price, 2)
                    cash += proceeds
                    all_fills.append(fill)
                    decisions.append(
                        Decision(
                            symbol=sym,
                            date=trade_date,
                            action="exit",
                            confidence=1.0,
                            reasons=[action.reason],
                            decision_id=_make_id(f"exit_{sym}_{trade_date}"),
                        )
                    )
                    positions.pop(sym, None)
                elif action.action_type == "partial_take":
                    if pos.quantity <= 0:
                        continue
                    oid = _make_id(f"partial_{sym}_{trade_date}")
                    fill = fill_partial_take(pos, bar, oid, config=fill_config)
                    if fill is None:
                        continue
                    sell_qty = int(abs(fill.quantity))
                    proceeds = round(sell_qty * fill.price, 2)
                    cash += proceeds
                    remaining = pos.quantity - sell_qty
                    updated = pos.model_copy(
                        update={
                            "quantity": remaining,
                            "market_value": remaining * fill.price,
                            "partial_taken": True,
                        }
                    )
                    positions[sym] = updated
                    decisions.append(
                        Decision(
                            symbol=sym,
                            date=trade_date,
                            action="partial_take",
                            confidence=1.0,
                            reasons=[action.reason],
                            decision_id=_make_id(f"partial_{sym}_{trade_date}"),
                        )
                    )

        # Regime + entries
        if len(positions) < len(symbols):
            spy_state = indicator_states.get("SPY")
            regime, regime_mult = detect_regime_and_multiplier(spy_state)

            all_considered = decide_candidates(
                list(all_bars.keys()),
                all_bars,
                indicator_states,
                trade_date,
                regime,
                mech_data,
            )
            candidates = [c for c in all_considered if c.block_reason is None]

            ranked = rank_candidates(
                candidates, len(symbols), len(positions), sector_map=sector_map
            )
            slots = len(symbols) - len(positions)

            for cand in ranked[:slots]:
                bar = date_bars.get(cand.symbol)
                state = indicator_states.get(cand.symbol)
                if bar is None or state is None:
                    continue
                prev = last_close.get(cand.symbol, 0.0)
                atr_val = compute_atr(state, bar.close)

                total_equity = cash + sum(
                    p.quantity * prices.get(p.symbol, 0.0) for p in positions.values()
                )
                sized = size_entry(total_equity, bar.close, atr_val, regime_mult, sizing_config)
                if sized is None:
                    continue
                final_shares = sized.shares

                order_id = _make_id(f"order_{cand.symbol}_{trade_date}")
                order = Order(
                    order_id=order_id,
                    symbol=cand.symbol,
                    action="buy",
                    quantity=float(final_shares),
                    order_type="market",
                    status="submitted",
                )
                fill = fill_entry_order(order, bar, prev, config=fill_config)
                if fill is None:
                    continue
                fill_price = fill.price
                cost = round(float(final_shares) * fill_price, 2)
                if cost > cash:
                    continue

                cash -= cost
                all_fills.append(fill)
                stop_price = round(fill_price - risk_config.stop_atr_mult * atr_val, 2)

                pos = Position(
                    symbol=cand.symbol,
                    quantity=float(final_shares),
                    entry_price=fill_price,
                    avg_cost=fill_price,
                    current_price=fill_price,
                    stop_price=stop_price,
                    market_value=cost,
                    decision_id=_make_id(f"entry_{cand.symbol}_{trade_date}"),
                    entry_date=trade_date,
                    high_since_entry=bar.high,
                )
                positions[cand.symbol] = pos
                decisions.append(
                    Decision(
                        symbol=cand.symbol,
                        date=trade_date,
                        action="enter",
                        confidence=cand.composite_score,
                        reasons=["replay"],
                        decision_id=_make_id(f"enter_{cand.symbol}_{trade_date}"),
                    )
                )

        # Mark to market
        total_mark = 0.0
        for sym, pos in positions.items():
            price = prices.get(sym)
            if price is not None:
                mv = round(pos.quantity * price, 2)
                total_mark += mv
                positions[sym] = pos.model_copy(update={"current_price": price, "market_value": mv})

        equity = round(cash + total_mark, 2)
        equity_curve.append(equity)

        for symbol, bar in date_bars.items():
            last_close[symbol] = bar.close

    # Compute metrics
    initial_equity = getattr(config.paper, "starting_equity", 100_000.0)
    total_return = (equity_curve[-1] - initial_equity) / initial_equity if equity_curve else 0.0
    years = len(equity_curve) / 252.0 if len(equity_curve) > 0 else 1.0
    cagr = (1.0 + total_return) ** (1.0 / years) - 1.0 if years > 0 else 0.0

    import numpy as np

    eq_arr = np.array(equity_curve) if equity_curve else np.array([initial_equity])
    peak = np.maximum.accumulate(eq_arr)
    dd = (eq_arr - peak) / peak
    max_dd = float(np.min(dd)) if len(dd) > 0 else 0.0

    output: dict[str, Any] = {
        "meta": {
            "command": "replay",
            "from_date": from_date,
            "to_date": to_date,
            "fixture_path": fixture_path,
            "fixture_hash": fixture_hash,
            "config_hash": config_hash,
        },
        "symbols": {
            "total": len(ensure_spy(list(all_bars.keys()))),
        },
        "decisions": [
            {
                "symbol": d.symbol,
                "date": str(d.date),
                "action": d.action,
                "confidence": d.confidence,
                "decision_id": d.decision_id,
            }
            for d in decisions
        ],
        "fills": [
            {
                "fill_id": f.fill_id,
                "symbol": f.symbol,
                "quantity": f.quantity,
                "price": f.price,
            }
            for f in all_fills
        ],
        "equity_curve": [{"day": i, "equity": round(e, 2)} for i, e in enumerate(equity_curve)],
        "metrics": {
            "total_return_pct": round(total_return * 100, 2),
            "cagr_pct": round(cagr * 100, 2),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "num_trades": len(decisions),
            "num_fills": len(all_fills),
        },
    }

    return output


def write_golden(output: dict[str, Any], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2, sort_keys=True))
    return path


def golden_hash(output: dict[str, Any]) -> str:
    raw = json.dumps(output, indent=2, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()

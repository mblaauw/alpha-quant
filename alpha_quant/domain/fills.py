"""Fill model — entry and stop-loss order execution simulation."""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from datetime import time as dtime

import structlog
from pydantic import BaseModel, ConfigDict

from alpha_quant.domain.models import Bar, CorporateAction, Fill, Order, Position, Quote

logger = structlog.get_logger()


class FillConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    slippage_bps: float = 5.0
    max_gap_pct: float = 0.02
    max_fill_pct: float = 1.0
    half_spread_default: float = 0.001


def make_fill_id(order_id: str, fill_date: date) -> str:
    raw = f"{order_id}|{fill_date.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _half_spread_pct(quote: Quote | None, config: FillConfig) -> float:
    if (
        quote is not None
        and quote.bid is not None
        and quote.ask is not None
        and quote.bid > 0
        and quote.ask > quote.bid
    ):
        mid = (quote.ask + quote.bid) / 2.0
        return (quote.ask - quote.bid) / (2.0 * mid)
    return config.half_spread_default


def _slippage_pct(quote: Quote | None, config: FillConfig) -> float:
    return config.slippage_bps / 10_000 + _half_spread_pct(quote, config)


def _market_open(bar_date: date) -> datetime:
    return datetime.combine(bar_date, dtime(9, 30))


def fill_entry_order(
    order: Order,
    bar: Bar,
    prev_close: float,
    quote: Quote | None = None,
    config: FillConfig | None = None,
) -> Fill | None:
    if order.action != "buy":
        return None

    cfg = config or FillConfig()

    if prev_close > 0:
        gap_pct = abs(bar.open - prev_close) / prev_close
        if gap_pct > cfg.max_gap_pct:
            return None

    slippage = _slippage_pct(quote=quote, config=cfg)
    fill_price = bar.open * (1.0 + slippage)
    fill_qty = int(order.quantity * cfg.max_fill_pct)
    if fill_qty <= 0:
        return None

    fill_id = make_fill_id(order.order_id, bar.date)

    return Fill(
        fill_id=fill_id,
        order_id=order.order_id,
        symbol=order.symbol,
        quantity=fill_qty,
        price=round(fill_price, 2),
        timestamp=_market_open(bar.date),
    )


def fill_stop_loss(
    position: Position,
    bar: Bar,
    order_id: str,
    quote: Quote | None = None,
    config: FillConfig | None = None,
) -> Fill | None:
    if position.stop_price is None:
        return None
    if bar.low > position.stop_price:
        return None

    cfg = config or FillConfig()
    slippage = _slippage_pct(quote=quote, config=cfg)
    fill_price = min(bar.open, position.stop_price) * (1.0 - slippage)
    fill_qty = position.quantity

    fill_id = make_fill_id(order_id, bar.date)

    return Fill(
        fill_id=fill_id,
        order_id=order_id,
        symbol=position.symbol,
        quantity=-fill_qty,
        price=round(fill_price, 2),
        timestamp=_market_open(bar.date),
    )


def fill_partial_take(
    position: Position,
    bar: Bar,
    order_id: str,
    quote: Quote | None = None,
    config: FillConfig | None = None,
) -> Fill | None:
    sell_qty = int(position.quantity * 0.5)
    if sell_qty <= 0:
        logger.debug("Skipping partial take — position too small", quantity=position.quantity)
        return None

    cfg = config or FillConfig()
    slippage = _slippage_pct(quote=quote, config=cfg)
    fill_price = bar.open * (1.0 - slippage)

    fill_id = make_fill_id(order_id, bar.date)

    return Fill(
        fill_id=fill_id,
        order_id=order_id,
        symbol=position.symbol,
        quantity=-sell_qty,
        price=round(fill_price, 2),
        timestamp=_market_open(bar.date),
    )


def apply_corporate_action(
    position: Position,
    ca: CorporateAction,
) -> Position:
    if ca.action_type == "split":
        if ca.ratio is None or ca.ratio <= 0:
            return position
        return position.model_copy(
            update={
                "quantity": int(position.quantity * ca.ratio),
                "avg_cost": round(position.avg_cost / ca.ratio, 6),
            }
        )

    if ca.action_type == "dividend":
        if ca.amount is None or ca.amount <= 0:
            return position
        new_cost = max(position.avg_cost - ca.amount, 0.0)
        return position.model_copy(
            update={
                "avg_cost": round(new_cost, 6),
            }
        )

    return position

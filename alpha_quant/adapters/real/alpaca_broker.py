"""AlpacaBroker — live trading via alpaca-py trading API."""

from datetime import UTC, datetime
from typing import Any, override

import structlog

from alpha_quant.domain.models import Fill, Order, Position
from alpha_quant.ports.broker import Broker

logger = structlog.get_logger()


class AlpacaBroker(Broker):
    def __init__(
        self, api_key: str, secret_key: str, base_url: str = "https://api.alpaca.markets"
    ) -> None:
        self._api_key = api_key
        self._secret_key = secret_key
        self._base_url = base_url

    def _get_trading_client(self) -> Any:
        from alpaca.trading.client import TradingClient

        return TradingClient(self._api_key, self._secret_key, paper=True)

    @override
    def submit_order(self, order: Order) -> Order:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        client = self._get_trading_client()
        side = OrderSide.BUY if order.action == "buy" else OrderSide.SELL
        req = MarketOrderRequest(
            symbol=order.symbol,
            qty=order.quantity,
            side=side,
            time_in_force=TimeInForce.DAY,
        )
        alpaca_order = client.submit_order(req)
        return Order(
            order_id=str(alpaca_order.id),
            symbol=str(alpaca_order.symbol),
            action=order.action,
            quantity=float(str(alpaca_order.qty)),
            order_type="market",
            status=str(alpaca_order.status),
            submitted_at=order.submitted_at,
            fill_date=datetime.now(UTC).date(),
            filled_quantity=float(str(alpaca_order.filled_qty)) if alpaca_order.filled_qty else 0.0,
            avg_fill_price=float(str(alpaca_order.filled_avg_price))
            if alpaca_order.filled_avg_price
            else None,
        )

    @override
    def cancel_order(self, order_id: str) -> bool:

        client = self._get_trading_client()
        try:
            client.cancel_order_by_id(order_id)
            return True
        except Exception:
            logger.exception("cancel_order_failed", order_id=order_id)
            return False

    @override
    def portfolio(self) -> dict:
        client = self._get_trading_client()
        account = client.get_account()
        return {
            "cash": float(str(account.cash)),
            "equity": float(str(account.equity)),
            "positions": 0,
        }

    @override
    def positions(self) -> list[Position]:
        client = self._get_trading_client()
        alpaca_positions = client.get_all_positions()
        return [
            Position(
                symbol=str(p.symbol),
                quantity=float(str(p.qty)),
                entry_price=float(str(p.avg_entry_price)) if p.avg_entry_price else None,
                avg_cost=float(str(p.avg_entry_price)) if p.avg_entry_price else 0.0,
                current_price=float(str(p.current_price)) if p.current_price else None,
                market_value=float(str(p.market_value)) if p.market_value else None,
                unrealized_pl=float(str(p.unrealized_pl)) if p.unrealized_pl else None,
            )
            for p in alpaca_positions
        ]

    @override
    def fills(self, since: str | None = None) -> list[Fill]:
        return []

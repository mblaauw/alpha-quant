"""Shared test fixtures and factory helpers."""

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Self

import pytest

from alpha_quant.domain.models import (
    Bar,
    CorporateAction,
    EarningsEntry,
    Fill,
    FundamentalsSnapshot,
    Order,
    Position,
    Quote,
)

# ---- Bar factory ----


@pytest.fixture
def bar() -> Bar:
    return Bar(
        symbol="AAPL",
        date=date(2026, 6, 11),
        open=100.0,
        high=105.0,
        low=95.0,
        close=100.0,
        volume=1_000_000,
    )


def make_bar(
    *,
    symbol: str = "AAPL",
    dt: date = date(2026, 6, 11),
    open_v: float = 100.0,
    high: float | None = None,
    low: float | None = None,
    close: float | None = None,
    volume: int = 1_000_000,
) -> Bar:
    h = high if high is not None else open_v + 5.0
    lo = low if low is not None else open_v - 5.0
    c = close if close is not None else open_v
    return Bar(symbol=symbol, date=dt, open=open_v, high=h, low=lo, close=c, volume=volume)


# ---- Order factory ----


@pytest.fixture
def order() -> Order:
    return Order(
        order_id="ord-001",
        symbol="AAPL",
        action="buy",
        quantity=100.0,
        order_type="market",
        status="submitted",
    )


def make_order(
    *,
    order_id: str = "ord-001",
    symbol: str = "AAPL",
    action: str = "buy",
    quantity: float = 100.0,
) -> Order:
    return Order(
        order_id=order_id,
        symbol=symbol,
        action=action,
        quantity=quantity,
        order_type="market",
        status="submitted",
    )


# ---- Position factory ----


@pytest.fixture
def position() -> Position:
    return Position(
        symbol="AAPL",
        quantity=100.0,
        entry_price=100.0,
        avg_cost=100.0,
        current_price=100.0,
        stop_price=90.0,
        market_value=10_000.0,
    )


def make_position(
    *,
    symbol: str = "AAPL",
    quantity: float = 100.0,
    avg_cost: float = 100.0,
    stop_price: float | None = 90.0,
    current_price: float | None = None,
) -> Position:
    cp = current_price if current_price is not None else avg_cost
    return Position(
        symbol=symbol,
        quantity=quantity,
        entry_price=avg_cost,
        avg_cost=avg_cost,
        current_price=cp,
        stop_price=stop_price,
        market_value=quantity * cp,
    )


# ---- Quote factory ----


@pytest.fixture
def quote() -> Quote:
    return Quote(
        symbol="AAPL",
        timestamp=datetime(2026, 6, 11, 9, 30),
        bid=99.0,
        ask=101.0,
    )


def make_quote(
    *,
    symbol: str = "AAPL",
    bid: float = 99.0,
    ask: float = 101.0,
) -> Quote:
    return Quote(
        symbol=symbol,
        timestamp=datetime(2026, 6, 11, 9, 30),
        bid=bid,
        ask=ask,
    )


# ---- Fundamentals factory ----


def make_fundamentals(**kwargs: float | None) -> FundamentalsSnapshot:
    return FundamentalsSnapshot(
        symbol=kwargs.get("symbol", "AAPL"),  # type: ignore[arg-type]
        as_of_date=date(2026, 6, 11),
        market_cap=kwargs.get("market_cap", 3_000_000_000_000.0),
        operating_cash_flow=kwargs.get("ocf", 100_000_000_000.0),
        total_liabilities=kwargs.get("total_liabilities", 250_000_000_000.0),
        total_debt=kwargs.get("total_debt", 50_000_000_000.0),
        total_equity=kwargs.get("total_equity", 200_000_000_000.0),
        net_income=kwargs.get("net_income", 50_000_000_000.0),
        accruals=kwargs.get("accruals", 0.0),
    )


# ---- Earnings factory ----


def make_earnings(
    symbol: str = "AAPL",
    dt: date = date(2026, 6, 11),
    eps_estimate: float | None = None,
    eps_actual: float | None = None,
) -> EarningsEntry:
    return EarningsEntry(
        symbol=symbol,
        date=dt,
        eps_estimate=eps_estimate,
        eps_actual=eps_actual,
    )


# ---- CorporateAction factory ----


def make_corp_action(
    *,
    symbol: str = "AAPL",
    action_type: str = "split",
    ratio: float | None = 4.0,
    amount: float | None = None,
) -> CorporateAction:
    return CorporateAction(
        symbol=symbol,
        effective_date=date(2026, 6, 11),
        action_type=action_type,
        ratio=ratio,
        amount=amount,
    )


# ---- Fill factory ----


def make_fill(
    *,
    fill_id: str = "fill-001",
    order_id: str = "ord-001",
    symbol: str = "AAPL",
    quantity: float = 100.0,
    price: float = 100.0,
) -> Fill:
    return Fill(
        fill_id=fill_id,
        order_id=order_id,
        symbol=symbol,
        quantity=quantity,
        price=price,
        timestamp=datetime(2026, 6, 11, 9, 30),
    )


# ---- FakeStore for pipeline tests ----


@dataclass
class FakeStore:
    bars: dict[str, list[Bar]] | None = None
    positions: list[Position] | None = None
    _saved_events: list[object] | None = None
    _saved_positions: list[Position] | None = None

    def load_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        return (self.bars or {}).get(symbol, [])

    def load_positions(self) -> list[Position]:
        return self.positions or []

    def load_latest_portfolio_snapshot(self) -> None:
        return None

    def save_position(self, pos: Position) -> None:
        if self._saved_positions is not None:
            self._saved_positions.append(pos)

    def save_fill(self, fill: object) -> None:
        pass

    def save_event(self, event: object) -> None:
        if self._saved_events is not None:
            self._saved_events.append(event)

    @contextmanager
    def transaction(self) -> Generator[Self]:
        yield self

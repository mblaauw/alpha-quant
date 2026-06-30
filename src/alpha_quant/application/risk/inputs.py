"""Risk input pipeline — load positions, returns, and compute covariance.

WS1 of the real risk engine epic (#612).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from alpha_quant.application.query import shared


@dataclass(frozen=True)
class RiskPosition:
    symbol: str
    shares: float
    market_value: float
    current_price: float
    weight: float
    sector: str


@dataclass(frozen=True)
class RiskInputs:
    as_of: datetime
    equity: float
    cash: float
    positions: list[RiskPosition]
    weights: list[float]
    symbols: list[str]
    sectors: list[str]
    halt_active: bool
    halt_reason: str | None
    halt_details: str | None


def load_inputs(
    book_id: str | None = None,
    lake: Any | None = None,
) -> RiskInputs:
    """Load all risk inputs for a book.

    Fetches positions with sector metadata from the store, computes equity,
    and optionally fetches return data from Alpha-Lake.
    """
    bid = UUID(book_id) if book_id else None

    def _query(uow):
        from alpha_quant.application.query.shared import resolve_active_book_id

        resolved_id = bid or resolve_active_book_id()
        halt = uow.store.current_halt(resolved_id)
        active_halt = halt if halt is not None and halt.halted else None

        positions_raw = uow.store.list_positions(resolved_id)
        portfolio = uow.store.load_portfolio(resolved_id)

        cash = float(portfolio.cash) if portfolio and portfolio.cash else 0.0
        total_mv = sum(float(p.market_value or 0) for p in positions_raw)
        equity = cash + total_mv if (cash + total_mv) > 0 else 0.0

        # Build sector map from security_reference
        from sqlalchemy import text

        sec_rows = uow.store.session.execute(
            text("SELECT symbol, sector FROM core.security_reference")
        ).fetchall()
        sector_map: dict[str, str] = {
            row._mapping["symbol"]: row._mapping["sector"] or "Unclassified" for row in sec_rows
        }

        positions: list[RiskPosition] = []
        weights: list[float] = []
        symbols: list[str] = []
        sectors: list[str] = []

        for p in positions_raw:
            mv = float(p.market_value or 0)
            price = float(p.current_price or 0)
            w = mv / equity if equity > 0 else 0.0
            sym = p.symbol
            sector = sector_map.get(sym, "Unclassified")
            positions.append(
                RiskPosition(
                    symbol=sym,
                    shares=float(p.quantity or 0),
                    market_value=mv,
                    current_price=price,
                    weight=w,
                    sector=sector,
                )
            )
            weights.append(w)
            symbols.append(sym)
            sectors.append(sector)

        return RiskInputs(
            as_of=datetime.now(UTC),
            equity=equity,
            cash=cash,
            positions=positions,
            weights=weights,
            symbols=symbols,
            sectors=sectors,
            halt_active=active_halt is not None,
            halt_reason=active_halt.reason.value if active_halt and active_halt.reason else None,
            halt_details=active_halt.details if active_halt else None,
        )

    return shared.with_uow(_query)

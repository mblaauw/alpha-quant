from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from alpha_quant.domain.exceptions import DataNormalizationError
from alpha_quant.domain.models import InsiderTransaction


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):  # fmt: skip
        return None


def _expect_type(raw: Any, expected: type, description: str, source: str = "normalize") -> None:
    if not isinstance(raw, expected):
        raise DataNormalizationError(
            f"Expected {description}, got {type(raw).__name__}",
            source=source,
            raw=str(raw)[:500],
        )


_TIMESTAMP_FMTS = ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y")


def _parse_date(value: str | None, *fmts: str) -> date | None:
    if not value:
        return None
    formats = fmts or _TIMESTAMP_FMTS
    for fmt in formats:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except (ValueError, TypeError):  # fmt: skip
            continue
    return None


def _latest_period(*quarters: dict[str, Any]) -> tuple[dict[str, Any], ...] | None:
    all_periods: set[str] = set()
    for q in quarters:
        all_periods.update(q.keys())
    if not all_periods:
        return None
    latest = max(all_periods)
    return tuple((q.get(latest, {}) or {}) for q in quarters)


def _cell_text(cells: list, index: int) -> str:
    if index >= len(cells):
        return ""
    return cells[index].text(strip=True)


def _parse_number(text: str | None) -> float | None:
    if not text:
        return None
    cleaned = re.sub(r"[^\d.,-]", "", text)
    cleaned = cleaned.replace(",", "")
    try:
        return float(cleaned)
    except (ValueError, TypeError):  # fmt: skip
        return None


def _parse_relationship(rel: str) -> str:
    if not rel:
        return ""
    if "officer" in rel and "director" in rel:
        return "officer,director"
    if "officer" in rel:
        return "officer"
    if "director" in rel:
        return "director"
    return rel


def _row_to_transaction(cells: list, fetch_id: str | None = None) -> InsiderTransaction | None:
    ticker = _cell_text(cells, 0).upper() or None
    owner = _cell_text(cells, 3) or ""
    title = _cell_text(cells, 4) or None
    tx_type = _cell_text(cells, 5).title() or None
    tx_date = _parse_date(_cell_text(cells, 6))
    filing_date = _parse_date(_cell_text(cells, 7))
    price = _parse_number(_cell_text(cells, 9))
    qty = _parse_number(_cell_text(cells, 10))
    held = _parse_number(_cell_text(cells, 11))

    if tx_type == "Sell":
        qty = -(qty or 0)

    if not ticker or qty is None or tx_date is None:
        return None

    return InsiderTransaction(
        symbol=ticker,
        filing_date=filing_date,
        transaction_date=tx_date,
        owner=owner,
        title=title,
        transaction_type=tx_type or "",
        shares_traded=qty,
        price=price,
        shares_held=held,
        fetch_id=fetch_id,
    )

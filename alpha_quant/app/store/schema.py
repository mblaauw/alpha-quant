"""Canonical dataset schemas and helpers.

Split from app/store.py — no behavior change.
"""

from typing import Any

import pyarrow as pa

_BAR_DATE_COL = "date"

_CANONICAL_SCHEMAS: dict[str, list[tuple[str, pa.DataType]]] = {
    "bars": [
        ("symbol", pa.string()),
        (_BAR_DATE_COL, pa.date32()),
        ("open", pa.float64()),
        ("high", pa.float64()),
        ("low", pa.float64()),
        ("close", pa.float64()),
        ("volume", pa.float64()),
        ("adj_close", pa.float64()),
        ("fetch_id", pa.string()),
    ],
    "fundamentals": [
        ("symbol", pa.string()),
        ("as_of_date", pa.date32()),
        ("market_cap", pa.float64()),
        ("pe_ratio", pa.float64()),
        ("eps_ttm", pa.float64()),
        ("dividend_yield", pa.float64()),
        ("sector", pa.string()),
        ("industry", pa.string()),
        ("operating_cash_flow", pa.float64()),
        ("total_liabilities", pa.float64()),
        ("total_debt", pa.float64()),
        ("total_equity", pa.float64()),
        ("revenue", pa.float64()),
        ("net_income", pa.float64()),
        ("accruals", pa.float64()),
        ("fetch_id", pa.string()),
    ],
    "insider_transactions": [
        ("symbol", pa.string()),
        ("filing_date", pa.date32()),
        ("transaction_date", pa.date32()),
        ("owner", pa.string()),
        ("title", pa.string()),
        ("transaction_type", pa.string()),
        ("shares_traded", pa.float64()),
        ("price", pa.float64()),
        ("shares_held", pa.float64()),
        ("fetch_id", pa.string()),
    ],
    "mentions": [
        ("symbol", pa.string()),
        ("mention_date", pa.date32()),
        ("source", pa.string()),
        ("count", pa.int64()),
        ("fetch_id", pa.string()),
    ],
    "corp_actions": [
        ("symbol", pa.string()),
        ("effective_date", pa.date32()),
        ("action_type", pa.string()),
        ("ratio", pa.float64()),
        ("amount", pa.float64()),
        ("fetch_id", pa.string()),
    ],
    "earnings": [
        ("symbol", pa.string()),
        ("date", pa.date32()),
        ("eps_estimate", pa.float64()),
        ("eps_actual", pa.float64()),
        ("revenue_estimate", pa.float64()),
        ("revenue_actual", pa.float64()),
        ("fetch_id", pa.string()),
    ],
}


def _maybe_fetch_id(m: object) -> str | None:
    return getattr(m, "fetch_id", None)


def model_to_pylist(models: list[Any], model_name: str) -> list[dict[str, Any]]:
    match model_name:
        case "bars":
            return [
                {
                    "symbol": m.symbol,
                    _BAR_DATE_COL: m.date,
                    "open": m.open,
                    "high": m.high,
                    "low": m.low,
                    "close": m.close,
                    "volume": m.volume,
                    "adj_close": m.adj_close,
                    "fetch_id": _maybe_fetch_id(m),
                }
                for m in models
            ]
        case "fundamentals":
            return [m.model_dump() for m in models] if models else []
        case "insider_transactions":
            return [
                {
                    "symbol": m.symbol,
                    "filing_date": m.filing_date,
                    "transaction_date": m.transaction_date,
                    "owner": m.owner,
                    "title": m.title,
                    "transaction_type": m.transaction_type,
                    "shares_traded": m.shares_traded,
                    "price": m.price,
                    "shares_held": m.shares_held,
                    "fetch_id": _maybe_fetch_id(m),
                }
                for m in models
            ]
        case "mentions":
            return [
                {
                    "symbol": m.symbol,
                    "mention_date": m.mention_date,
                    "source": m.source,
                    "count": m.count,
                    "fetch_id": _maybe_fetch_id(m),
                }
                for m in models
            ]
        case "corp_actions":
            return [
                {
                    "symbol": m.symbol,
                    "effective_date": m.effective_date,
                    "action_type": m.action_type,
                    "ratio": m.ratio,
                    "amount": m.amount,
                    "fetch_id": _maybe_fetch_id(m),
                }
                for m in models
            ]
        case "earnings":
            return [
                {
                    "symbol": m.symbol,
                    "date": m.date,
                    "eps_estimate": m.eps_estimate,
                    "eps_actual": m.eps_actual,
                    "revenue_estimate": m.revenue_estimate,
                    "revenue_actual": m.revenue_actual,
                    "fetch_id": _maybe_fetch_id(m),
                }
                for m in models
            ]
        case _:
            return [m.model_dump() for m in models]


def partition_col(model_name: str) -> str:
    mapping = {
        "bars": _BAR_DATE_COL,
        "fundamentals": "as_of_date",
        "insider_transactions": "filing_date",
        "mentions": "mention_date",
        "corp_actions": "effective_date",
        "earnings": "date",
    }
    return mapping.get(model_name, "date")


def dedup_keys(dataset: str) -> str:
    mapping = {
        "bars": "symbol, date",
        "fundamentals": "symbol, as_of_date",
        "insider_transactions": (
            "symbol, filing_date, transaction_date, transaction_type,"
            " owner, shares_traded, price, shares_held"
        ),
        "mentions": "symbol, mention_date, source",
        "corp_actions": "symbol, effective_date, action_type",
        "earnings": "symbol, date",
    }
    return mapping.get(dataset, "rowid")


def get_schema(dataset: str) -> pa.Schema:
    fields = _CANONICAL_SCHEMAS[dataset]
    return pa.schema([pa.field(name, typ, nullable=typ != pa.date32()) for name, typ in fields])

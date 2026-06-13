from __future__ import annotations

import json
from datetime import UTC, date, datetime

import structlog

from alpha_quant.domain._normalize_helpers import (
    _float,
    _latest_period,
    _parse_date,
)
from alpha_quant.domain.models import (
    Bar,
    EarningsEntry,
    FundamentalsSnapshot,
    Quote,
    TickerRecord,
)

logger = structlog.get_logger()

_BAR_DATE_FMT = "%Y-%m-%d"
_EARNINGS_DATE_FMT = "%Y-%m-%d"
_TIMESTAMP_FMTS = ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y")


def normalize_eodhd_bars(raw: bytes | str, symbol: str) -> list[Bar] | None:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning("normalize_eodhd_bars_parse_failed", error=str(exc))
        return None
    if not isinstance(data, list):
        logger.warning("normalize_eodhd_bars_unexpected_type", got=type(data).__name__)
        return None
    bars: list[Bar] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        try:
            bar_date = datetime.strptime(entry["date"], _BAR_DATE_FMT).date()
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("normalize_eodhd_bars_invalid_date", error=str(exc))
            continue
        bars.append(
            Bar(
                symbol=symbol,
                date=bar_date,
                open=_float(entry.get("open")) or 0.0,
                high=_float(entry.get("high")) or 0.0,
                low=_float(entry.get("low")) or 0.0,
                close=_float(entry.get("close")) or 0.0,
                adj_close=_float(entry.get("adjusted_close")),
                volume=_float(entry.get("volume")) or 0.0,
            )
        )
    return bars if bars else None


def normalize_eodhd_fundamentals(
    raw: bytes | str, symbol: str, today: date | None = None
) -> FundamentalsSnapshot | None:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning("normalize_eodhd_fundamentals_parse_failed", error=str(exc))
        return None
    if not isinstance(data, dict):
        logger.warning("normalize_eodhd_fundamentals_unexpected_type", got=type(data).__name__)
        return None

    general = data.get("General", {}) or {}
    highlights = data.get("Highlights", {}) or {}

    as_of_str = general.get("LastUpdated") or general.get("Date")
    if as_of_str:
        parsed = _parse_date(as_of_str)
        if parsed is not None:
            as_of_date = parsed
        else:
            return None
    else:
        return None

    financials = data.get("Financials", {}) or {}
    balance = financials.get("Balance_Sheet", {}).get("quarterly", {}) or {}
    income = financials.get("Income_Statement", {}).get("quarterly", {}) or {}
    cash_flow = financials.get("Cash_Flow", {}).get("quarterly", {}) or {}

    latest = _latest_period(balance, income, cash_flow)
    if latest is not None:
        bq, iq, cq = latest
    else:
        bq = iq = cq = {}

    net_income = _float(iq.get("netIncome"))
    op_cf = _float(cq.get("operatingCashFlow"))
    accruals = (net_income - op_cf) if (net_income is not None and op_cf is not None) else None

    return FundamentalsSnapshot(
        symbol=symbol,
        as_of_date=as_of_date,
        market_cap=_float(highlights.get("MarketCapitalization")),
        pe_ratio=_float(highlights.get("PERatio")),
        eps_ttm=_float(highlights.get("EPS")),
        dividend_yield=_float(highlights.get("DividendYield")),
        sector=(general.get("Sector") or "").strip() or None,
        industry=(general.get("Industry") or "").strip() or None,
        operating_cash_flow=op_cf,
        total_liabilities=_float(bq.get("totalLiabilities")),
        total_debt=_float(bq.get("totalDebt")),
        total_equity=_float(bq.get("totalEquity")),
        revenue=_float(iq.get("revenue")),
        net_income=net_income,
        accruals=accruals,
    )


def normalize_eodhd_earnings(raw: bytes | str) -> list[EarningsEntry] | None:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning("normalize_eodhd_earnings_parse_failed", error=str(exc))
        return None
    if not isinstance(data, dict):
        logger.warning("normalize_eodhd_earnings_unexpected_type", got=type(data).__name__)
        return None
    entries = data.get("earnings", [])
    if not isinstance(entries, list):
        logger.warning("normalize_eodhd_earnings_not_a_list")
        return None

    results: list[EarningsEntry] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        try:
            entry_date = datetime.strptime(entry["date"], _EARNINGS_DATE_FMT).date()
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("normalize_eodhd_earnings_invalid_date", error=str(exc))
            continue
        results.append(
            EarningsEntry(
                symbol=entry.get("code", ""),
                date=entry_date,
                eps_estimate=_float(entry.get("eps_estimate")),
                eps_actual=_float(entry.get("eps_actual")),
                revenue_estimate=_float(entry.get("revenue_estimate")),
                revenue_actual=_float(entry.get("revenue_actual")),
            )
        )
    return results if results else None


def normalize_alpaca_quote(raw: bytes | str, symbol: str) -> Quote | None:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning("normalize_alpaca_quote_parse_failed", error=str(exc))
        return None
    if not isinstance(data, dict):
        logger.warning("normalize_alpaca_quote_unexpected_type", got=type(data).__name__)
        return None

    quotes = data.get("quotes", {})
    if not isinstance(quotes, dict):
        logger.warning("normalize_alpaca_quote_no_quotes_dict")
        return None

    raw_quote = quotes.get(symbol)
    if not isinstance(raw_quote, dict):
        logger.warning("normalize_alpaca_quote_symbol_not_found", symbol=symbol)
        return None

    bid = _float(raw_quote.get("bid_price"))
    ask = _float(raw_quote.get("ask_price"))
    mid = ((bid + ask) / 2) if (bid is not None and ask is not None) else None

    ts = raw_quote.get("timestamp")
    timestamp: datetime | None = None
    if ts is not None:
        try:
            if isinstance(ts, str):
                timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            else:
                timestamp = ts
        except (ValueError, TypeError) as exc:
            logger.warning("normalize_alpaca_quote_invalid_timestamp", error=str(exc))

    if timestamp is None:
        return None

    return Quote(
        symbol=symbol,
        timestamp=timestamp.astimezone(UTC),
        price=mid,
        bid=bid,
        ask=ask,
        bid_size=_float(raw_quote.get("bid_size")),
        ask_size=_float(raw_quote.get("ask_size")),
        volume=_float(raw_quote.get("volume")),
    )


def normalize_sec_tickers(raw: bytes | str) -> dict[str, TickerRecord] | None:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning("normalize_sec_tickers_parse_failed", error=str(exc))
        return None
    if not isinstance(data, dict):
        logger.warning("normalize_sec_tickers_unexpected_type", got=type(data).__name__)
        return None

    result: dict[str, TickerRecord] = {}
    for entry in data.values():
        if not isinstance(entry, dict):
            continue
        ticker = (entry.get("ticker") or "").strip().upper()
        cik_raw = entry.get("cik_str")
        title = (entry.get("title") or "").strip()
        if not ticker or not cik_raw or not title:
            continue
        cik = str(int(cik_raw)).zfill(10)
        result[ticker] = TickerRecord(
            ticker=ticker,
            cik=cik,
            name=title,
        )
    return result if result else None

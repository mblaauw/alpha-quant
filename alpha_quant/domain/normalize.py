from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import UTC, date, datetime
from statistics import mean, stdev
from typing import Any

import structlog
from selectolax.parser import HTMLParser

from alpha_quant.domain.exceptions import DataNormalizationError
from alpha_quant.domain.models import (
    Bar,
    EarningsEntry,
    FundamentalsSnapshot,
    InsiderTransaction,
    MentionCount,
    Quote,
    SentimentBaseline,
    TickerRecord,
)

logger = structlog.get_logger()

_COMMON_WORDS: set[str] = {
    "AI",
    "AM",
    "APR",
    "AT",
    "ATM",
    "AUG",
    "CEO",
    "CFO",
    "COO",
    "CTO",
    "DD",
    "DEC",
    "DJT",
    "DM",
    "DOE",
    "EU",
    "EV",
    "FEB",
    "FO",
    "GO",
    "IAN",
    "IMO",
    "IRL",
    "IT",
    "JAN",
    "JUL",
    "JUN",
    "LA",
    "LOL",
    "MAR",
    "MAY",
    "MO",
    "NOV",
    "NTA",
    "NY",
    "OCT",
    "OH",
    "OK",
    "OMG",
    "OP",
    "OR",
    "PE",
    "PM",
    "RH",
    "ROI",
    "SA",
    "SEC",
    "SEP",
    "SO",
    "TA",
    "TL",
    "TLDR",
    "TV",
    "UK",
    "USA",
    "USD",
    "VIP",
    "VS",
    "YE",
    "YTD",
    "YOLO",
}

_BAR_DATE_FMT = "%Y-%m-%d"
_EARNINGS_DATE_FMT = "%Y-%m-%d"
_TIMESTAMP_FMTS = ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y")


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError, TypeError:
        return None


def _expect_type(raw: Any, expected: type, description: str) -> None:
    if not isinstance(raw, expected):
        raise DataNormalizationError(
            f"Expected {description}, got {type(raw).__name__}",
            source="normalize",
            raw=str(raw)[:500],
        )


def _parse_date(value: str | None, *fmts: str) -> date | None:
    if not value:
        return None
    formats = fmts or _TIMESTAMP_FMTS
    for fmt in formats:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError, TypeError:
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


def normalize_eodhd_fundamentals(raw: bytes | str, symbol: str) -> FundamentalsSnapshot | None:
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
    as_of_date = date.today()
    if as_of_str:
        parsed = _parse_date(as_of_str)
        if parsed is not None:
            as_of_date = parsed

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

    return Quote(
        symbol=symbol,
        timestamp=timestamp.astimezone(UTC) if timestamp is not None else datetime.now(UTC),
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
    except ValueError, TypeError:
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


def _row_to_transaction(cells: list) -> InsiderTransaction | None:
    ticker_el = cells[0].css_first("a")
    if ticker_el is None:
        return None
    ticker = ticker_el.text(strip=True).upper()
    if not ticker:
        return None

    owner = _cell_text(cells, 1)
    title = _cell_text(cells, 2)

    rel = _cell_text(cells, 3).lower()
    rel = _parse_relationship(rel)

    tx_type = _cell_text(cells, 4).strip().lower()
    if tx_type and tx_type not in ("buy", "sell"):
        return None

    price_text = _cell_text(cells, 5)
    price = _parse_number(price_text)

    qty_text = _cell_text(cells, 6)
    qty = _parse_number(qty_text)

    date_text = _cell_text(cells, 8)
    tx_date = _parse_date(date_text)

    if not ticker or qty is None:
        return None

    return InsiderTransaction(
        symbol=ticker,
        filing_date=tx_date or date.today(),
        transaction_date=tx_date,
        owner=owner or "Unknown",
        title=title,
        transaction_type=("Buy" if tx_type == "buy" else "Sell"),
        shares_traded=qty if tx_type == "buy" else -qty,
        price=price,
    )


def normalize_openinsider_html(raw: bytes | str) -> list[InsiderTransaction] | None:
    html = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw

    parser = HTMLParser(html)
    rows = parser.css("table.tinytable tbody tr")
    if not rows:
        rows = parser.css("table.tinytable tr")
    if not rows:
        logger.warning("normalize_openinsider_no_rows_found")
        return None

    transactions: list[InsiderTransaction] = []
    for row in rows:
        cells = row.css("td")
        if len(cells) < 10:
            continue
        try:
            tx = _row_to_transaction(cells)
            if tx is not None:
                transactions.append(tx)
        except Exception as exc:
            logger.debug("normalize_openinsider_skip_row", error=str(exc))
            continue
    return transactions if transactions else None


def normalize_reddit_mentions(
    raw: bytes | str, symbols: list[str], subreddit: str = "reddit"
) -> list[MentionCount] | None:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning("normalize_reddit_mentions_parse_failed", error=str(exc))
        return None

    children = data.get("data", {}).get("children", [])
    if not isinstance(children, list):
        logger.warning("normalize_reddit_mentions_no_children")
        return None

    posts = [c["data"] for c in children if isinstance(c, dict) and isinstance(c.get("data"), dict)]

    patterns = {
        sym: re.compile(rf"\b{re.escape(sym)}\b", re.IGNORECASE)
        for sym in symbols
        if sym not in _COMMON_WORDS
    }

    counts: dict[str, int] = defaultdict(int)
    for post in posts:
        title = (post.get("title") or "") or ""
        selftext = (post.get("selftext") or "") or ""
        text = f"{title} {selftext}".upper()
        for sym, pattern in patterns.items():
            matches = pattern.findall(text)
            if matches:
                counts[sym] += len(matches)

    today = date.today()
    results = [
        MentionCount(symbol=sym, date=today, source=subreddit, count=count)
        for sym, count in counts.items()
        if count > 0
    ]
    return results if results else None


def calculate_sentiment_baseline(counts: list[MentionCount], symbol: str) -> SentimentBaseline:
    relevant = [c.count for c in counts if c.symbol.upper() == symbol.upper()]
    if len(relevant) < 2:
        return SentimentBaseline(
            symbol=symbol.upper(),
            mean_mentions=float(sum(relevant)) if relevant else 0.0,
            std_mentions=0.0,
            z_score=0.0,
        )

    avg = mean(relevant)
    sd = stdev(relevant)
    current = relevant[-1]
    z = (current - avg) / sd if sd > 0 else 0.0
    return SentimentBaseline(
        symbol=symbol.upper(),
        mean_mentions=avg,
        std_mentions=sd,
        z_score=round(z, 4),
    )

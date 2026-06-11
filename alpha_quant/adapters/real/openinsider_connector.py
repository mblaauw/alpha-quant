import re
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import structlog
from selectolax.parser import HTMLParser

from alpha_quant.adapters.real.base_connector import BaseConnector
from alpha_quant.domain.models import InsiderCluster, InsiderTransaction

logger = structlog.get_logger()

SCREENER_URL = "http://openinsider.com/screener"


class OpenInsiderConnector(BaseConnector):
    def __init__(
        self,
        *,
        user_agent: str = "",
        vault_base: Path | None = None,
    ) -> None:
        super().__init__(
            source_name="openinsider",
            base_url="http://openinsider.com",
            tokens_per_second=0.33,
            max_burst=1,
            user_agent=user_agent,
            vault_base=vault_base,
        )

    def parse(self, data: bytes, **kwargs: Any) -> Any:
        return data

    def _build_screener_url(self, days: int) -> str:
        start = (date.today() - timedelta(days=days)).isoformat()
        params = {
            "s": "",
            "o": "",
            "fc": "",
            "fd": start,
            "fdr": f"{days}",
            "td": "",
            "tdr": "",
            "pl": "",
            "ph": "",
            "ll": "",
            "lh": "",
            "vl": "",
            "vh": "",
            "ocl": "",
            "och": "",
            "sic1": "",
            "sicl": "",
            "sicoh": "",
            "sl": "",
            "sh": "",
            "sml": "",
            "smh": "",
            "iscal": "",
            "iscab": "",
            "iba": "",
            "hor": "",
            "exc": "",
            "cnt": "1000",
            "rnd": "",
        }
        return f"{SCREENER_URL}?{urlencode(params)}"

    def _fetch_html(self, days: int) -> str:
        url = self._build_screener_url(days)
        response = self.fetch(url)
        return response.text

    def _parse_transactions(self, html: str) -> list[InsiderTransaction]:
        parser = HTMLParser(html)
        rows = parser.css("table.tinytable tbody tr")
        if not rows:
            rows = parser.css("table.tinytable tr")
        if not rows:
            logger.warning("openinsider_no_rows_found")
            return []

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
                logger.debug("openinsider_skip_row", error=str(exc))
                continue
        return transactions

    def _cluster_transactions(self, transactions: list[InsiderTransaction]) -> list[InsiderCluster]:
        groups: dict[str, list[InsiderTransaction]] = {}
        for tx in transactions:
            groups.setdefault(tx.symbol, []).append(tx)

        clusters: list[InsiderCluster] = []
        for symbol, txs in groups.items():
            if not txs:
                continue
            dates = [tx.transaction_date or tx.filing_date for tx in txs]
            prices = [tx.price for tx in txs if tx.price is not None]

            net_shares = sum(tx.shares_traded for tx in txs)
            type_counter = Counter(tx.transaction_type for tx in txs)
            dominant_type = type_counter.most_common(1)[0][0] if type_counter else None
            total_value = sum((tx.price or 0) * tx.shares_traded for tx in txs)
            officer_names = {tx.owner for tx in txs if tx.title and "officer" in tx.title.lower()}
            director_names = {tx.owner for tx in txs if tx.title and "director" in tx.title.lower()}

            avg_price = (sum(prices) / len(prices)) if prices else None
            cluster = InsiderCluster(
                symbol=symbol,
                cluster_date=max(dates),
                num_transactions=len(txs),
                net_shares=net_shares,
                avg_price=avg_price,
                value=total_value,
                transaction_type=dominant_type,
                officer_count=len(officer_names),
                director_count=len(director_names),
            )
            clusters.append(cluster)
        return clusters

    def recent_clusters(self, days: int = 30) -> list[InsiderCluster]:
        html = self._fetch_html(days)
        transactions = self._parse_transactions(html)
        return self._cluster_transactions(transactions)

    def cluster_for_symbol(self, symbol: str, days: int = 30) -> InsiderCluster | None:
        clusters = self.recent_clusters(days)
        for c in clusters:
            if c.symbol.upper() == symbol.upper():
                return c
        return None


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


def _parse_date(text: str | None) -> date | None:
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError, TypeError:
            continue
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

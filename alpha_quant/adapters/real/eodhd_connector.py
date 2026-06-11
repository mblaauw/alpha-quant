from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from alpha_quant.adapters.real.base_connector import BaseConnector
from alpha_quant.domain.exceptions import DataNormalizationError
from alpha_quant.domain.models import Bar, EarningsEntry, FundamentalsSnapshot

if TYPE_CHECKING:
    from alpha_quant.app.vault import Vault


class EODHDConnector(BaseConnector):
    def __init__(
        self,
        *,
        api_token: str,
        base_url: str = "https://eodhd.com/api",
        tokens_per_second: float = 10.0,
        max_burst: float = 20.0,
        user_agent: str = "",
        vault: Vault | None = None,
    ) -> None:
        self._api_token = api_token
        super().__init__(
            source_name="eodhd",
            base_url=base_url,
            tokens_per_second=tokens_per_second,
            max_burst=max_burst,
            user_agent=user_agent,
            vault=vault,
        )

    def _build_url(self, path: str) -> str:
        base = self._base_url.rstrip("/")
        return f"{base}/{path.lstrip('/')}"

    def _params(self, **extra: str) -> dict[str, str]:
        return {"api_token": self._api_token, "fmt": "json", **extra}

    def _get_json(self, path: str, params: dict[str, str] | None = None) -> Any:
        url = self._build_url(path)
        merged = self._params(**(params or {}))
        response = self.fetch(url, merged)
        return response.json()

    def parse(self, data: bytes, **kwargs: Any) -> Any:
        return data

    def daily_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        raw = self._get_json(
            f"eod/{symbol}",
            {"from": start.isoformat(), "to": end.isoformat()},
        )
        if not isinstance(raw, list):
            raise DataNormalizationError(
                "Expected list of bars",
                source="eodhd",
                raw=str(raw)[:500],
            )
        bars: list[Bar] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                bar_date = datetime.strptime(entry["date"], "%Y-%m-%d").date()
            except (KeyError, ValueError, TypeError) as e:
                raise DataNormalizationError(
                    f"Invalid bar date: {e}",
                    source="eodhd",
                    raw=str(entry)[:500],
                ) from e
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
        return bars

    def fundamentals_snapshot(self, symbol: str) -> FundamentalsSnapshot:
        raw = self._get_json(f"fundamentals/{symbol}")
        if not isinstance(raw, dict):
            raise DataNormalizationError(
                "Expected dict for fundamentals",
                source="eodhd",
                raw=str(raw)[:500],
            )

        general = raw.get("General", {}) or {}
        highlights = raw.get("Highlights", {}) or {}

        as_of_str = general.get("LastUpdated") or general.get("Date")
        as_of_date = date.today()
        if as_of_str:
            parsed = _parse_date(as_of_str)
            if parsed is not None:
                as_of_date = parsed

        financials = raw.get("Financials", {}) or {}
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

    def earnings_calendar(self, start: date, end: date) -> list[EarningsEntry]:
        raw = self._get_json(
            "calendar/earnings",
            {"from": start.isoformat(), "to": end.isoformat()},
        )
        if not isinstance(raw, dict):
            raise DataNormalizationError(
                "Expected dict for earnings calendar",
                source="eodhd",
                raw=str(raw)[:500],
            )
        entries = raw.get("earnings", [])
        if not isinstance(entries, list):
            raise DataNormalizationError(
                "Expected 'earnings' list",
                source="eodhd",
                raw=str(raw)[:500],
            )
        results: list[EarningsEntry] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            try:
                entry_date = datetime.strptime(entry["date"], "%Y-%m-%d").date()
            except (KeyError, ValueError, TypeError) as e:
                raise DataNormalizationError(
                    f"Invalid earnings date: {e}",
                    source="eodhd",
                    raw=str(entry)[:500],
                ) from e
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
        return results

    def bulk_last_day(self, exchange: str = "US") -> list[Bar]:
        raw = self._get_json(f"eod-bulk-last-day/{exchange}")
        if not isinstance(raw, list):
            raise DataNormalizationError(
                "Expected list for bulk_last_day",
                source="eodhd",
                raw=str(raw)[:500],
            )
        bars: list[Bar] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            try:
                bar_date = datetime.strptime(entry["date"], "%Y-%m-%d").date()
            except (KeyError, ValueError, TypeError) as e:
                raise DataNormalizationError(
                    f"Invalid bulk bar date: {e}",
                    source="eodhd",
                    raw=str(entry)[:500],
                ) from e
            bars.append(
                Bar(
                    symbol=entry.get("code", ""),
                    date=bar_date,
                    open=_float(entry.get("open")) or 0.0,
                    high=_float(entry.get("high")) or 0.0,
                    low=_float(entry.get("low")) or 0.0,
                    close=_float(entry.get("close")) or 0.0,
                    adj_close=_float(entry.get("adjusted_close")),
                    volume=_float(entry.get("volume")) or 0.0,
                )
            )
        return bars


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError, TypeError:
        return None


def _parse_date(value: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
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

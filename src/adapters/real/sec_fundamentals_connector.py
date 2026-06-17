from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any, override

from adapters.real.base_connector import BaseConnector
from domain.models import EarningsEntry, FundamentalsSnapshot
from ports.fundamentals import Fundamentals

if TYPE_CHECKING:
    from adapters.real.sec_connector import SECConnector
    from app.vault import Vault

SEC_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


class SECFundamentalsConnector(BaseConnector, Fundamentals):
    """SEC EDGAR CompanyFacts fundamentals adapter.

    Uses the free public XBRL API at data.sec.gov. CIK resolution is
    delegated to an injected SECConnector instance (reuses its SQLite cache).
    """

    def __init__(
        self,
        sec_cik: SECConnector,
        *,
        user_agent: str = "",
        tokens_per_second: float = 10.0,
        max_burst: float = 5.0,
        vault: Vault | None = None,
    ) -> None:
        self._sec_cik = sec_cik
        super().__init__(
            source_name="sec_edgar",
            base_url="https://data.sec.gov",
            tokens_per_second=tokens_per_second,
            max_burst=max_burst,
            user_agent=user_agent,
            vault=vault,
        )

    # ── CIK resolution ────────────────────────────────────────────────────────

    def _cik(self, symbol: str) -> str | None:
        tickers = self._sec_cik.ticker_map()
        record = tickers.get(symbol.upper())
        return record.cik if record else None

    # ── XBRL helpers ──────────────────────────────────────────────────────────

    def _latest_annual(self, facts: dict[str, Any], concept: str) -> float | None:
        """Return the latest annual value for a US-GAAP concept."""
        units_data = self._get_units(facts, concept)
        if not units_data:
            return None
        fy_entries = [e for e in units_data if e.get("fp") == "FY"]
        if not fy_entries:
            return None
        fy_entries.sort(key=lambda e: e.get("end") or "", reverse=True)
        return fy_entries[0].get("val")

    def _sum_quarterly(self, facts: dict[str, Any], concept: str, years: int = 1) -> float | None:
        """Sum the last N years of quarterly values for a concept (e.g., TTM EPS)."""
        units_data = self._get_units(facts, concept)
        if not units_data:
            return None
        q_entries = [e for e in units_data if (e.get("fp") or "").startswith("Q")]
        if not q_entries:
            return None
        q_entries.sort(key=lambda e: e.get("end") or "", reverse=True)
        selected = q_entries[: years * 4]
        return sum(e.get("val", 0) for e in selected) if selected else None

    def _sum_annual(self, facts: dict[str, Any], *concepts: str) -> float | None:
        """Sum the latest annual values of multiple concepts (e.g., total debt)."""
        total = 0.0
        found = False
        for concept in concepts:
            val = self._latest_annual(facts, concept)
            if val is not None:
                total += val
                found = True
        return total if found else None

    @staticmethod
    def _get_units(facts: dict[str, Any], concept: str) -> list[dict[str, Any]]:
        us_gaap = facts.get("us-gaap", {})
        entry = us_gaap.get(concept, {})
        units_data = None
        for unit_key in ("USD", "USD/shares", "shares", "pure"):
            ud = entry.get("units", {}).get(unit_key)
            if ud is not None:
                units_data = ud
                break
        if units_data is None and entry.get("units"):
            units_data = next(iter(entry["units"].values()), None)
        return units_data or []

    # ── Fundamentals port ─────────────────────────────────────────────────────

    @override
    def snapshot(self, symbol: str) -> FundamentalsSnapshot:
        cik = self._cik(symbol)
        if cik is None:
            return FundamentalsSnapshot(symbol=symbol, as_of_date=date.today())

        url = SEC_COMPANY_FACTS_URL.format(cik=cik)
        response = self.fetch(url)
        raw: dict[str, Any] = response.json()
        facts = raw.get("facts", {})

        eps_ttm = self._sum_quarterly(facts, "EarningsPerShareDiluted")
        net_income = self._latest_annual(facts, "NetIncomeLoss")
        revenue = self._latest_annual(facts, "Revenues")
        if revenue is None:
            revenue = self._latest_annual(
                facts, "RevenueFromContractWithCustomerExcludingAssessedTax"
            )
        op_cf = self._latest_annual(facts, "NetCashProvidedByOperatingActivities")
        if op_cf is None:
            op_cf = self._latest_annual(
                facts, "NetCashProvidedByOperatingActivitiesContinuingOperations"
            )
        if op_cf is None:
            op_cf = self._latest_annual(facts, "NetCashProvidedByUsedInOperatingActivities")
        total_debt = self._sum_annual(facts, "LongTermDebtNoncurrent", "ShortTermBorrowings")
        total_equity = self._latest_annual(facts, "StockholdersEquity")
        total_liabilities = self._latest_annual(facts, "Liabilities")

        accruals = (net_income - op_cf) if (net_income is not None and op_cf is not None) else None

        as_of_date = date.today()
        end_dates = []
        for concept in ("NetIncomeLoss", "RevenueFromContractWithCustomerExcludingAssessedTax"):
            ud = self._get_units(facts, concept)
            if ud:
                for e in ud:
                    end_str = e.get("end")
                    if end_str:
                        try:  # noqa: SIM105
                            end_dates.append(datetime.strptime(end_str, "%Y-%m-%d").date())
                        except (ValueError, TypeError):  # fmt: skip
                            pass
        if end_dates:
            as_of_date = max(end_dates)

        return FundamentalsSnapshot(
            symbol=symbol,
            as_of_date=as_of_date,
            eps_ttm=eps_ttm,
            net_income=net_income,
            revenue=revenue,
            operating_cash_flow=op_cf,
            total_debt=total_debt,
            total_equity=total_equity,
            total_liabilities=total_liabilities,
            accruals=accruals,
            adapter="sec_edgar",
        )

    @override
    def earnings_calendar(self, start: date, end: date) -> list[EarningsEntry]:
        return []

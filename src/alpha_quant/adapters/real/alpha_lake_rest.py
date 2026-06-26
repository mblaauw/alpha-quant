from __future__ import annotations

from datetime import date, datetime
from typing import Any, override

import httpx

from alpha_quant.adapters._parse import (
    parse_bar_obs,
    parse_earnings_obs,
    parse_fundamental_obs,
    parse_insider_obs,
    parse_mention_obs,
    parse_symbol_observations,
)
from alpha_quant.contracts.alpha_lake import (
    AlphaLakeContract,
    AlphaLakeHealth,
    DecisionPanel,
    MarketObservations,
    NeutralObservations,
    SymbolObservations,
    SymbolPanel,
    UniverseMember,
    UniverseSnapshot,
)
from alpha_quant.ports.alpha_lake import AlphaLakeReadPort


class AlphaLakeRestClient(AlphaLakeReadPort):
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str = "",
        timeout_s: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"X-API-Key": api_key} if api_key else {}
        self._client = httpx.Client(timeout=httpx.Timeout(timeout_s))

    @override
    def health(self) -> AlphaLakeHealth:
        try:
            resp = self._client.get(f"{self._base_url}/v1/health", headers=self._headers)
            if resp.status_code == 200:
                data = resp.json()
                return AlphaLakeHealth(
                    status=data.get("status", "ok"),
                    snapshots=data.get("snapshots", 0),
                    latest_snapshot_id=data.get("latest_snapshot_id"),
                )
            return AlphaLakeHealth(status="error")
        except httpx.HTTPError:
            return AlphaLakeHealth(status="unreachable")

    @override
    def contract(self) -> AlphaLakeContract:
        resp = self._client.get(f"{self._base_url}/v1/contract", headers=self._headers)
        resp.raise_for_status()
        data = resp.json()
        return AlphaLakeContract(
            service=data["service"],
            api_version=data["api_version"],
            minimum_alpha_quant_version=data["minimum_alpha_quant_version"],
            capabilities=data.get("capabilities", []),
        )

    @override
    def read_universe(self, as_of: date | None = None) -> UniverseSnapshot:
        params: dict[str, str] = {}
        if as_of:
            params["as_of"] = as_of.isoformat()
        resp = self._client.get(
            f"{self._base_url}/v1/universe",
            headers=self._headers,
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        return UniverseSnapshot(
            as_of=as_of,
            members=[UniverseMember(**m) for m in data.get("members", [])],
        )

    @override
    def read_decision_panel(
        self,
        symbols: list[str],
        as_of: datetime,
        snapshot_id: str | None = None,
    ) -> DecisionPanel:
        return _legacy_panel(self._fetch_panel_data, symbols, as_of, snapshot_id)

    @override
    def read_replay_panel(
        self,
        symbols: list[str],
        as_of: datetime,
        snapshot_id: str,
    ) -> DecisionPanel:
        return _legacy_panel(self._fetch_panel_data, symbols, as_of, snapshot_id)

    @override
    def read_observations(
        self,
        symbols: list[str],
        as_of: datetime,
        snapshot_id: str | None = None,
    ) -> NeutralObservations:
        data = self._fetch_panel_data(symbols, as_of, snapshot_id)
        return _build_neutral_observations(data, symbols, as_of, snapshot_id)

    @override
    def close(self) -> None:
        self._client.close()

    def _fetch_panel_data(
        self,
        symbols: list[str],
        as_of: datetime,
        snapshot_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str] = {
            "symbols": ",".join(symbols),
            "as_of": as_of.isoformat(),
        }
        if snapshot_id:
            params["snapshot_id"] = snapshot_id
        resp = self._client.get(
            f"{self._base_url}/v1/decision-panel",
            headers=self._headers,
            params=params,
        )
        resp.raise_for_status()
        return resp.json()


def _legacy_panel(
    fetcher: Any,
    symbols: list[str],
    as_of: datetime,
    snapshot_id: str | None = None,
) -> DecisionPanel:
    data = fetcher(symbols, as_of, snapshot_id)
    panels: dict[str, SymbolPanel] = {}
    for symbol, raw in data.get("panels", {}).items():
        bars = [parse_bar_obs(b) for b in raw.get("bars", [])]
        indicators = _legacy_parse_indicators(raw.get("indicators", {}))
        fundamentals = [parse_fundamental_obs(m) for m in raw.get("fundamentals", [])]
        insider = [parse_insider_obs(t) for t in raw.get("insider_transactions", [])]
        earnings = [parse_earnings_obs(e) for e in raw.get("earnings_events", [])]
        mentions = [parse_mention_obs(m) for m in raw.get("attention_mentions", [])]
        panels[symbol] = SymbolPanel(
            symbol=symbol,
            bars=bars,
            indicators=indicators,
            fundamentals=fundamentals,
            insider_transactions=insider,
            earnings_events=earnings,
            attention_mentions=mentions,
        )
    return DecisionPanel(
        as_of=as_of,
        snapshot_id=snapshot_id,
        symbols=symbols,
        panels=panels,
    )


def _build_neutral_observations(
    data: dict[str, Any],
    symbols: list[str],
    as_of: datetime,
    snapshot_id: str | None = None,
) -> NeutralObservations:
    per_symbol: dict[str, SymbolObservations] = {}
    for symbol, raw in data.get("panels", {}).items():
        per_symbol[symbol] = parse_symbol_observations(symbol, raw)

    spy_obs = per_symbol.get("SPY")
    return NeutralObservations(
        as_of=as_of,
        snapshot_id=snapshot_id,
        symbols=symbols,
        per_symbol=per_symbol,
        market=MarketObservations.from_symbol_observations(spy_obs),
    )


def _legacy_parse_indicators(raw: dict[str, list[Any]]) -> dict[str, list[float | None]]:
    result: dict[str, list[float | None]] = {}
    for key, values in raw.items():
        if key in (
            "effective_date",
            "security_id",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "source_id",
        ):
            continue
        result[key] = [float(v) if v is not None else None for v in values]
    return result

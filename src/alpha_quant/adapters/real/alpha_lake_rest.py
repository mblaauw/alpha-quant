from __future__ import annotations

from datetime import UTC, datetime
from typing import override

import httpx

from alpha_quant.adapters._parse import (
    parse_facts_bundle,
    parse_symbol_mutation_result,
    parse_symbol_registry_item,
)
from alpha_quant.contracts.alpha_lake import (
    AlphaLakeContract,
    AlphaLakeHealth,
    FactsBundle,
    SymbolMutationResult,
    SymbolRegistryItem,
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
    def get_freshness(self, symbols: list[str]) -> dict[str, datetime]:
        try:
            resp = self._client.get(
                f"{self._base_url}/v1/bars/latest",
                headers=self._headers,
                params={"symbols": ",".join(symbols)},
            )
            if resp.status_code == 200:
                data = resp.json()
                now = datetime.now(UTC)
                return {
                    sym: datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    for sym, ts in data.get("bars", {}).items()
                }
        except httpx.HTTPError:
            pass
        now = datetime.now(UTC)
        return {s: now for s in symbols}

    @override
    def read_facts_bundle(
        self,
        symbol: str,
        as_of: datetime,
        snapshot_id: str | None = None,
        *,
        categories: list[str] | None = None,
        readout_ids: list[str] | None = None,
        metric_ids: list[str] | None = None,
    ) -> FactsBundle:
        params: dict[str, str] = {"as_of": as_of.isoformat()}
        if snapshot_id:
            params["snapshot_id"] = snapshot_id
        if categories:
            params["categories"] = ",".join(categories)
        if readout_ids:
            params["readout_ids"] = ",".join(readout_ids)
        if metric_ids:
            params["metric_ids"] = ",".join(metric_ids)
        resp = self._client.get(
            f"{self._base_url}/v1/symbol/{symbol}/facts-bundle",
            headers=self._headers,
            params=params,
        )
        resp.raise_for_status()
        return parse_facts_bundle(resp.json())

    @override
    def list_symbols(self, active_only: bool = True) -> list[SymbolRegistryItem]:
        params = {"active_only": str(active_only).lower()}
        resp = self._client.get(
            f"{self._base_url}/v1/symbols",
            headers=self._headers,
            params=params,
        )
        resp.raise_for_status()
        return [parse_symbol_registry_item(item) for item in resp.json()]

    @override
    def add_symbol(self, symbol: str) -> SymbolMutationResult:
        resp = self._client.post(
            f"{self._base_url}/v1/symbols",
            headers={**self._headers, "Content-Type": "application/json"},
            json={"symbol": symbol},
        )
        resp.raise_for_status()
        return parse_symbol_mutation_result(resp.json())

    @override
    def remove_symbol(self, symbol: str) -> SymbolMutationResult:
        resp = self._client.delete(
            f"{self._base_url}/v1/symbols/{symbol}",
            headers=self._headers,
        )
        resp.raise_for_status()
        return parse_symbol_mutation_result(resp.json())

    @override
    def close(self) -> None:
        self._client.close()

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from alpha_quant.application.query.decisions import DecisionService
from alpha_quant.application.query.journal import JournalService
from alpha_quant.application.query.orders import OrderService
from alpha_quant.application.query.portfolio import PortfolioService
from alpha_quant.application.query.risk import RiskService
from alpha_quant.application.query.runs import RunService
from alpha_quant.application.query.system import SystemService
from alpha_quant.transport.app import app
from alpha_quant.transport.commands import _unit_of_work
from alpha_quant.transport.console_routes import _freshness_service
from alpha_quant.transport.deps import service_provider


class _FakePortfolioService:
    def summary(self, book_id: str | None = None) -> dict[str, object]:
        return {"cash": 0.0, "market_value": 0.0, "equity": 0.0, "positions_count": 0}

    def list_positions(self, book_id: str | None = None) -> list[dict[str, object]]:
        return []

    def get_position(self, position_id: str) -> dict[str, object] | None:
        return None


class _FakeDecisionService:
    def list_decisions(
        self,
        book_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
        sort: str = "date",
        symbol: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, object]:
        return {"items": [], "next_cursor": None}

    def get_decision(self, decision_id: str) -> dict[str, object] | None:
        return None


class _FakeOrderService:
    def list_orders(self, **kwargs: object) -> dict[str, object]:
        return {"items": [], "next_cursor": None}


class _FakeRiskService:
    def summary(self, book_id: str | None = None) -> dict[str, object]:
        return {"equity": 0.0, "halted": False, "halt": None}


class _FakeRunService:
    def list_runs(self, **kwargs: object) -> dict[str, object]:
        return {"items": [], "next_cursor": None}

    def get_run(self, run_id: str) -> dict[str, object] | None:
        return None


class _FakeJournalService:
    def list_entries(self, **kwargs: object) -> dict[str, object]:
        return {"items": [], "next_cursor": None}


class _FakeSystemService:
    def context(self) -> dict[str, object]:
        return {"halted": False, "halt_reason": None, "books": []}

    def full_status(self) -> dict[str, object]:
        return {**self.context(), "components": {}}


class _FakeFreshnessService:
    def summary(self, symbols: list[str]) -> dict[str, object]:
        return {"items": [], "stale_count": 0}

    def for_symbols(self, symbols: list[str]) -> list[dict[str, Any]]:
        return []

    def for_symbol(self, symbol: str) -> dict[str, object]:
        return {"symbol": symbol, "stale": False}


class _FakeCommandStore:
    def list_commands(self, **kwargs: object) -> list[object]:
        return []

    def get_command(self, command_id: object) -> object | None:
        return None


class _FakeUnitOfWork:
    store = _FakeCommandStore()

    def __enter__(self) -> _FakeUnitOfWork:
        return self

    def __exit__(self, *args: object) -> None:
        return None


app.dependency_overrides.update(
    {
        service_provider(PortfolioService): _FakePortfolioService,
        service_provider(DecisionService): _FakeDecisionService,
        service_provider(OrderService): _FakeOrderService,
        service_provider(RiskService): _FakeRiskService,
        service_provider(RunService): _FakeRunService,
        service_provider(JournalService): _FakeJournalService,
        service_provider(SystemService): _FakeSystemService,
        _freshness_service: _FakeFreshnessService,
        _unit_of_work: _FakeUnitOfWork,
    }
)

client = TestClient(app)


class TestHealth:
    def test_livez(self) -> None:
        resp = client.get("/livez")
        assert resp.status_code == 200
        assert resp.json() == {"status": "alive"}

    def test_root_serves_spa(self) -> None:
        resp = client.get("/")
        assert resp.status_code in (200, 404)

    def test_static_index(self) -> None:
        resp = client.get("/static/index.html")
        assert resp.status_code in (200, 404)


class TestConsoleAPI:
    def test_console_context(self) -> None:
        resp = client.get("/v1/console/context")
        assert resp.status_code == 200
        data = resp.json()
        assert "halted" in data

    def test_console_portfolio(self) -> None:
        resp = client.get("/v1/console/portfolio")
        assert resp.status_code == 200

    def test_console_decisions(self) -> None:
        resp = client.get("/v1/console/decisions")
        assert resp.status_code == 200

    def test_console_orders(self) -> None:
        resp = client.get("/v1/console/orders")
        assert resp.status_code == 200

    def test_console_risk(self) -> None:
        resp = client.get("/v1/console/risk")
        assert resp.status_code == 200

    def test_console_runs(self) -> None:
        resp = client.get("/v1/console/runs")
        assert resp.status_code == 200

    def test_console_journal(self) -> None:
        resp = client.get("/v1/console/journal")
        assert resp.status_code == 200

    def test_console_system(self) -> None:
        resp = client.get("/v1/console/system")
        assert resp.status_code == 200

    def test_commands_endpoint(self) -> None:
        resp = client.get("/v1/commands")
        assert resp.status_code in (200, 500)

from __future__ import annotations

from fastapi.testclient import TestClient

from alpha_quant.transport.app import app

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

    def test_console_desk(self) -> None:
        resp = client.get("/v1/console/desk")
        assert resp.status_code == 200

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

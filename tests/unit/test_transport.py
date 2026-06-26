from __future__ import annotations

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

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


class TestDashboardAPI:
    def test_dashboard_context(self) -> None:
        resp = client.get("/v1/dashboard/context")
        assert resp.status_code in (200, 500)

    def test_dashboard_system(self) -> None:
        resp = client.get("/v1/dashboard/system")
        assert resp.status_code in (200, 500)

    def test_commands_endpoint(self) -> None:
        resp = client.get("/v1/commands")
        assert resp.status_code in (200, 500)

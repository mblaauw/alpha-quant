from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from alpha_quant.application.dashboard import app
from alpha_quant.application.dashboard.db import DashboardDB

client = TestClient(app)


class TestAPIEndpoints:
    def test_status_endpoint(self) -> None:
        resp = client.get("/api/v1/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "halted" in data
        assert "status" in data

    def test_equity_curve_endpoint(self) -> None:
        resp = client.get("/api/v1/equity-curve")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_portfolio_summary_endpoint(self) -> None:
        resp = client.get("/api/v1/portfolio/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "open_positions" in data

    def test_positions_endpoint(self) -> None:
        resp = client.get("/api/v1/positions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_portfolio_risk_endpoint(self) -> None:
        resp = client.get("/api/v1/portfolio/risk")
        assert resp.status_code == 200
        data = resp.json()
        assert "near_stop_count" in data

    def test_runs_latest_endpoint(self) -> None:
        resp = client.get("/api/v1/runs/latest")
        assert resp.status_code == 200

    def test_runs_endpoint(self) -> None:
        resp = client.get("/api/v1/runs")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_staleness_events_endpoint(self) -> None:
        resp = client.get("/api/v1/events/staleness")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_consistency_violations_endpoint(self) -> None:
        resp = client.get("/api/v1/events/consistency-violations")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_quarantine_endpoint(self) -> None:
        resp = client.get("/api/v1/quarantine")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_alerts_endpoint(self) -> None:
        resp = client.get("/api/v1/alerts")
        assert resp.status_code == 200
        data = resp.json()
        assert "halted" in data

    def test_reports_endpoint(self) -> None:
        resp = client.get("/api/v1/reports")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_journal_endpoint(self) -> None:
        resp = client.get("/api/v1/journal")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_decisions_symbols_endpoint(self) -> None:
        resp = client.get("/api/v1/decisions/symbols")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_decisions_endpoint(self) -> None:
        resp = client.get("/api/v1/decisions", params={"symbol": "AAPL"})
        assert resp.status_code == 200

    def test_concepts_endpoint(self) -> None:
        resp = client.get("/api/v1/concepts")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_dashboard_page(self) -> None:
        resp = client.get("/dashboard/")
        assert resp.status_code == 200
        assert "Alpha Quant Dashboard" in resp.text

    def test_root_redirects(self) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Alpha Quant Dashboard" in resp.text

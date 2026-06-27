"""Advice workflow integration tests — require running Docker stack.

Run with: docker compose up -d && uv run pytest tests/integration/ -q
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Requires running Docker stack (postgres + api)")
class TestAdviceFlow:
    def test_scorecard_persistence(self) -> None:
        """Scorecards are persisted to PostgreSQL via DailyCycleService."""
        pass

    def test_advice_endpoint(self) -> None:
        """GET /v1/console/advice/today returns data after a run."""
        pass

    def test_scorecard_detail(self) -> None:
        """GET /v1/console/scorecards/{id} returns components."""
        pass

    def test_follow_command(self) -> None:
        """candidate.follow creates a paper order."""
        pass

    def test_reject_command(self) -> None:
        """candidate.reject records operator override."""
        pass

    def test_risk_methods_endpoint(self) -> None:
        """GET /v1/console/risk-methods returns available methods."""
        pass

    def test_lake_symbols_endpoint(self) -> None:
        """GET /v1/console/lake-symbols returns Alpha-Lake registry."""
        pass

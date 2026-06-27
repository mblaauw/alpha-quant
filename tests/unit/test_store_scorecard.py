"""Store method tests — validate signatures and module imports.

Full integration tests against PostgreSQL are run via Docker.
"""

from __future__ import annotations

from alpha_quant.adapters.postgres.operational_store import PostgresOperationalStore
from alpha_quant.domain.scorecard import Scorecard, ScorecardComponent


class TestStoreInterface:
    def test_save_scorecard_exists(self) -> None:
        assert hasattr(PostgresOperationalStore, "save_scorecard")
        assert callable(PostgresOperationalStore.save_scorecard)

    def test_load_scorecard_exists(self) -> None:
        assert hasattr(PostgresOperationalStore, "load_scorecard")
        assert callable(PostgresOperationalStore.load_scorecard)

    def test_load_scorecards_for_run_exists(self) -> None:
        assert hasattr(PostgresOperationalStore, "load_scorecards_for_run")
        assert callable(PostgresOperationalStore.load_scorecards_for_run)

    def test_save_advice_artifact_exists(self) -> None:
        assert hasattr(PostgresOperationalStore, "save_advice_artifact")
        assert callable(PostgresOperationalStore.save_advice_artifact)

    def test_save_operator_override_exists(self) -> None:
        assert hasattr(PostgresOperationalStore, "save_operator_override")
        assert callable(PostgresOperationalStore.save_operator_override)

    def test_list_risk_methods_exists(self) -> None:
        assert hasattr(PostgresOperationalStore, "list_risk_methods")
        assert callable(PostgresOperationalStore.list_risk_methods)

    def test_set_book_risk_profile_exists(self) -> None:
        assert hasattr(PostgresOperationalStore, "set_book_risk_profile")
        assert callable(PostgresOperationalStore.set_book_risk_profile)

    def test_update_position_risk_exists(self) -> None:
        assert hasattr(PostgresOperationalStore, "update_position_risk")
        assert callable(PostgresOperationalStore.update_position_risk)

    def test_domain_models_import(self) -> None:
        from alpha_quant.domain.advice import (
            AdviceAction,
            AdviceArtifact,
            AdviceRecommendation,
            OperatorOverride,
        )
        from alpha_quant.domain.scorecard import (
            ComponentState,
            Recommendation,
        )

        assert AdviceAction is not None
        assert AdviceArtifact is not None
        assert AdviceRecommendation is not None
        assert OperatorOverride is not None
        assert ComponentState is not None
        assert Recommendation is not None

    def test_scorecard_constructs(self) -> None:
        s = Scorecard(
            symbol="AAPL",
            security_id="sec-1",
        )
        assert s.symbol == "AAPL"

    def test_scorecard_component_constructs(self) -> None:
        c = ScorecardComponent(name="test", category="x", score=50.0)
        assert c.score == 50.0

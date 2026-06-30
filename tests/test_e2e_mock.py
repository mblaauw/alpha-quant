"""End-to-end test with full mock data — cycle, advice, sizing, M1-M8, config.

Uses FakeOperationalStore, AlphaLakeHttpFixtureClient, VirtualClock, and
CannedLLM to simulate a complete DailyCycleService run and verifies every
output that the Desk GUI depends on.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

import pytest

from alpha_quant.adapters.fake.alpha_lake_http_fixture import AlphaLakeHttpFixtureClient
from alpha_quant.adapters.fake.canned_llm import CannedLLM
from alpha_quant.adapters.fake.operational_store import FakeOperationalStore
from alpha_quant.adapters.fake.virtual_clock import VirtualClock

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


class TestE2EMock:
    """Full end-to-end test against fixture data with all adapters mocked."""

    @pytest.fixture
    def store(self) -> FakeOperationalStore:
        return FakeOperationalStore()

    @pytest.fixture
    def lake(self) -> AlphaLakeHttpFixtureClient:
        return AlphaLakeHttpFixtureClient(FIXTURES_DIR / "v1")

    @pytest.fixture
    def clock(self) -> VirtualClock:
        return VirtualClock(datetime(2026, 1, 5, 14, 0, 0).date())

    @pytest.fixture
    def llm(self) -> CannedLLM:
        return CannedLLM()

    # ── DailyCycleService full cycle ──────────────────────────────────

    def test_daily_cycle_produces_scorecards_and_marks(
        self, store: FakeOperationalStore, lake: AlphaLakeHttpFixtureClient, clock: VirtualClock
    ) -> None:
        """DailyCycleService.run() produces scorecards and portfolio marks."""
        from alpha_quant.application.daily_cycle import DailyCycleService

        service = DailyCycleService(lake, store, clock)
        book_id = UUID("00000000-0000-0000-0000-000000000001")
        as_of = datetime(2026, 1, 5, 14, 0, 0)

        result = service.run(
            book_id=book_id,
            as_of=as_of,
            run_key="e2e-test",
            discovery_symbols=["AAPL", "MSFT"],
        )

        assert result.scorecard_count > 0, "No scorecards produced"
        assert result.decision_run_id is not None
        assert not result.halted, "System should not be halted"

        scorecards = store.load_scorecards_for_run(str(result.decision_run_id))
        assert len(scorecards) == result.scorecard_count

        for sc in scorecards:
            assert sc.symbol, "Scorecard missing symbol"
            assert sc.config_hash, "Scorecard missing config_hash"
            assert sc.strategy_version, "Scorecard missing strategy_version"
            assert sc.total_score >= 0, f"Negative score for {sc.symbol}"
            assert sc.components, f"No components for {sc.symbol}"

    def test_daily_cycle_with_llm_produces_advice(
        self,
        store: FakeOperationalStore,
        lake: AlphaLakeHttpFixtureClient,
        clock: VirtualClock,
        llm: CannedLLM,
    ) -> None:
        """DailyCycleService with LLM produces AdviceArtifact rows."""
        from alpha_quant.application.daily_cycle import DailyCycleService

        service = DailyCycleService(lake, store, clock, llm=llm)
        book_id = UUID("00000000-0000-0000-0000-000000000001")
        as_of = datetime(2026, 1, 5, 14, 0, 0)

        result = service.run(
            book_id=book_id,
            as_of=as_of,
            run_key="e2e-advice-test",
            discovery_symbols=["AAPL", "MSFT"],
        )

        scorecards = store.load_scorecards_for_run(str(result.decision_run_id))
        advice_count = len(store._advice_artifacts)

        assert advice_count > 0, "No advice artifacts produced"
        # Each scorecard produces 1 overall advice + 1 overall explanation + N stage explanations
        assert advice_count >= len(scorecards) * 3, (
            f"Expected at least {len(scorecards) * 3} advice artifacts (1 overall + 1 explanation + stages)"
            f" per scorecard, got {advice_count}"
        )

        for artifact in store._advice_artifacts.values():
            assert artifact.validation_status in ("verified", "unverified", "failed"), (
                f"Invalid validation_status: {artifact.validation_status}"
            )
            assert artifact.recommendation is not None
            assert artifact.recommendation.headline, "Advice missing headline"

        # Verify stage explanations exist
        stage_artifacts = [
            a for a in store._advice_artifacts.values() if a.scope == "scorecard_stage"
        ]
        assert len(stage_artifacts) > 0, "No stage explanation artifacts produced"
        for sa in stage_artifacts:
            assert sa.scope_id in ("M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8"), (
                f"Invalid stage scope_id: {sa.scope_id}"
            )
            assert artifact.recommendation.summary, "Advice missing summary"
            assert artifact.deterministic_differs is not None

    # ── Scorecard component invariants ────────────────────────────────

    def test_all_components_have_metrics(
        self, store: FakeOperationalStore, lake: AlphaLakeHttpFixtureClient, clock: VirtualClock
    ) -> None:
        """Every ScorecardComponent has populated details_json."""
        from alpha_quant.application.daily_cycle import DailyCycleService

        service = DailyCycleService(lake, store, clock)
        book_id = UUID("00000000-0000-0000-0000-000000000001")
        as_of = datetime(2026, 1, 5, 14, 0, 0)

        result = service.run(
            book_id=book_id,
            as_of=as_of,
            run_key="e2e-metrics-test",
            discovery_symbols=["AAPL"],
        )

        scorecards = store.load_scorecards_for_run(str(result.decision_run_id))
        for sc in scorecards:
            for comp in sc.components:
                assert comp.details_json != "{}", f"{comp.name} has empty details_json"
                details = json.loads(comp.details_json)
                metrics = details.get("metrics", [])
                assert len(metrics) > 0, f"{comp.name} has no metrics"

    def test_score_scores_in_0_100(
        self, store: FakeOperationalStore, lake: AlphaLakeHttpFixtureClient, clock: VirtualClock
    ) -> None:
        """All component scores are in [0, 100] and total_score >= 0."""
        from alpha_quant.application.daily_cycle import DailyCycleService

        service = DailyCycleService(lake, store, clock)
        book_id = UUID("00000000-0000-0000-0000-000000000001")
        as_of = datetime(2026, 1, 5, 14, 0, 0)

        result = service.run(
            book_id=book_id,
            as_of=as_of,
            run_key="e2e-range-test",
            discovery_symbols=["AAPL", "MSFT", "NVDA"],
        )

        scorecards = store.load_scorecards_for_run(str(result.decision_run_id))
        for sc in scorecards:
            assert sc.total_score >= 0, f"Negative total_score for {sc.symbol}"
            for comp in sc.components:
                assert 0.0 <= comp.score <= 100.0, f"{comp.name} score {comp.score} not in [0, 100]"

    # ── M1-M8 mapping completeness ────────────────────────────────────

    def test_all_categories_mapped_to_m_module(
        self, store: FakeOperationalStore, lake: AlphaLakeHttpFixtureClient, clock: VirtualClock
    ) -> None:
        """Every scorecard component category has an M1-M8 mapping."""
        from alpha_quant.application.daily_cycle import DailyCycleService
        from alpha_quant.domain.categories import resolve_mid

        service = DailyCycleService(lake, store, clock)
        book_id = UUID("00000000-0000-0000-0000-000000000001")
        as_of = datetime(2026, 1, 5, 14, 0, 0)

        result = service.run(
            book_id=book_id,
            as_of=as_of,
            run_key="e2e-cat-test",
            discovery_symbols=["AAPL"],
        )

        scorecards = store.load_scorecards_for_run(str(result.decision_run_id))
        for sc in scorecards:
            for comp in sc.components:
                mid, _, _ = resolve_mid(comp.category)
                assert mid, (
                    f"Component '{comp.name}' with category '{comp.category}' has no M1-M8 mapping"
                )

    # ── Mock mode via command bus ─────────────────────────────────────

    # ── Config audit trail ────────────────────────────────────────────

    def test_config_change_writes_audit_event(self, store: FakeOperationalStore) -> None:
        """config_set produces an audit_event entry."""
        store.config_set("e2e_test_key", "e2e_test_value")

        matching = [e for e in store._audit_events if e.event_type == "config.e2e_test_key.changed"]
        assert len(matching) == 1, f"Expected 1 audit event, got {len(matching)}"
        assert "e2e_test_key" in matching[0].payload_json
        assert "e2e_test_value" in matching[0].payload_json

    # ── CannedLLM valid JSON ─────────────────────────────────────────

    def test_canned_llm_parses_as_valid_advice(self, llm: CannedLLM) -> None:
        """CannedLLM response parses as valid AdviceRecommendation."""
        from alpha_quant.application.explanation import ExplanationService
        from alpha_quant.domain.scorecard import (
            Scorecard,
            Recommendation,
            ComponentState,
            ScorecardComponent,
        )

        service = ExplanationService(llm)
        sc = Scorecard(
            symbol="AAPL",
            total_score=75.0,
            recommendation=Recommendation.add,
            confidence=0.75,
            data_quality=ComponentState.pass_,
            components=[
                ScorecardComponent(
                    name="momentum",
                    category="technical",
                    score=80.0,
                    state=ComponentState.pass_,
                    weight=0.12,
                    passed=True,
                    reason="Strong momentum",
                ),
            ],
            config_hash="abc123",
            strategy_version="1.0",
        )
        artifact = service.generate_scorecard_explanation(sc)

        assert artifact.validation_status == "verified"
        rec = artifact.recommendation
        assert rec is not None
        assert rec.headline
        assert rec.summary
        assert rec.confidence_label in ("low", "medium", "high")
        assert isinstance(rec.key_reasons, list)
        assert isinstance(rec.main_risks, list)
        assert isinstance(rec.what_changed, list)
        assert isinstance(rec.override_guidance, list)
        assert artifact.input_hash
        assert artifact.output_hash
        assert artifact.deterministic_differs is not None

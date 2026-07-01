"""Unit tests for ExplanationService."""

from __future__ import annotations

from alpha_quant.application.explanation import ExplanationService
from alpha_quant.domain.advice import (
    ExplanationScope,
    ExplanationStatus,
    AdviceRecommendation,
    CalculationSnapshot,
)
from alpha_quant.domain.scorecard import (
    Recommendation,
    ComponentState,
    Scorecard,
    ScorecardComponent,
)


class TestExplanationModels:
    def test_explanation_scope_values(self) -> None:
        assert ExplanationScope.scorecard_stage == "scorecard_stage"
        assert ExplanationScope.scorecard_overall == "scorecard_overall"
        assert ExplanationScope.risk_category == "risk_category"
        assert ExplanationScope.risk_overall == "risk_overall"
        assert ExplanationScope.final_output == "final_output"

    def test_explanation_status_values(self) -> None:
        assert ExplanationStatus.current == "current"
        assert ExplanationStatus.recalculating == "recalculating"
        assert ExplanationStatus.stale == "stale"
        assert ExplanationStatus.unavailable == "unavailable"

    def test_calculation_snapshot_defaults(self) -> None:
        cs = CalculationSnapshot()
        assert cs.snapshot_id == ""
        assert cs.facts_hash == ""
        assert cs.config_hash == ""


class TestExplanationService:
    def test_compute_input_fingerprint(self) -> None:
        from alpha_quant.adapters.fake.canned_llm import CannedLLM

        llm = CannedLLM()
        svc = ExplanationService(llm)
        fp1 = svc.compute_input_fingerprint({"a": 1, "b": 2})
        fp2 = svc.compute_input_fingerprint({"b": 2, "a": 1})
        fp3 = svc.compute_input_fingerprint({"a": 1, "b": 3})
        assert fp1 == fp2, "Same dict should produce same fingerprint"
        assert fp1 != fp3, "Different values should produce different fingerprints"

    def test_make_snapshot(self) -> None:
        from alpha_quant.adapters.fake.canned_llm import CannedLLM

        llm = CannedLLM()
        svc = ExplanationService(llm)
        sc = Scorecard(
            symbol="AAPL",
            facts_hash="abc123",
            config_hash="def456",
            strategy_version="1.0",
        )
        snap = svc.make_snapshot(sc)
        assert "snapshot_id" in snap
        assert snap["facts_hash"] == "abc123"
        assert snap["config_hash"] == "def456"

    def test_validate_recommendation_valid(self) -> None:
        rec = AdviceRecommendation(
            recommendation=Recommendation.hold,
            confidence_label="medium",
            headline="Test headline",
            summary="Test summary",
            key_reasons=["Test reason"],
        )
        assert ExplanationService._validate_recommendation(rec) == "verified"

    def test_validate_recommendation_invalid_action(self) -> None:
        rec = AdviceRecommendation(
            recommendation=Recommendation.hold,
            confidence_label="invalid_level",
        )
        assert ExplanationService._validate_recommendation(rec) == "failed"

    def test_fallback_recommendation(self) -> None:
        fb = ExplanationService._fallback_recommendation(Recommendation.hold)
        assert fb.recommendation == Recommendation.hold
        assert fb.confidence_label == "low"
        assert "Deterministic" in fb.headline

    def test_parse_llm_response_valid(self) -> None:
        from alpha_quant.adapters.fake.canned_llm import CannedLLM

        llm = CannedLLM()
        svc = ExplanationService(llm)
        raw = (
            '{"headline": "Strong setup", "summary": "Test",'
            ' "recommended_action": "hold", "confidence_label": "high",'
            ' "interpretation": "Test interpretation",'
            ' "key_evidence": ["evidence 1"], "key_caveats": ["caveat 1"]}'
        )
        result = svc._parse_llm_response(raw)
        assert result is not None
        assert result.headline == "Strong setup"
        assert result.interpretation == "Test interpretation"
        assert result.key_evidence == ["evidence 1"]
        assert result.key_caveats == ["caveat 1"]

    def test_parse_llm_response_invalid_json(self) -> None:
        from alpha_quant.adapters.fake.canned_llm import CannedLLM

        llm = CannedLLM()
        svc = ExplanationService(llm)
        result = svc._parse_llm_response("not json")
        assert result is None

    def test_generate_stage_explanations(self) -> None:
        from alpha_quant.adapters.fake.canned_llm import CannedLLM

        llm = CannedLLM()
        svc = ExplanationService(llm)
        sc = Scorecard(
            symbol="AAPL",
            recommendation=Recommendation.hold,
            confidence=0.7,
            total_score=65.0,
            facts_hash="abc",
            config_hash="def",
            components=[
                ScorecardComponent(name="technical_trend", category="technical", score=80.0),
                ScorecardComponent(name="fundamentals", category="fundamental", score=30.0),
            ],
        )
        artifacts = svc.generate_stage_explanations(sc)
        assert len(artifacts) > 0
        for a in artifacts:
            assert a.scope == ExplanationScope.scorecard_stage
            assert a.scope_id in ("M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8")
            assert a.snapshot_id != ""
            assert a.input_fingerprint != ""

    def test_generate_scorecard_explanation(self) -> None:
        from alpha_quant.adapters.fake.canned_llm import CannedLLM

        llm = CannedLLM()
        svc = ExplanationService(llm)
        sc = Scorecard(
            symbol="AAPL",
            recommendation=Recommendation.hold,
            confidence=0.7,
            total_score=65.0,
            facts_hash="abc",
            config_hash="def",
        )
        artifact = svc.generate_scorecard_explanation(sc)
        assert artifact.scope == ExplanationScope.scorecard_overall
        assert artifact.snapshot_id != ""
        assert artifact.input_fingerprint != ""

    def test_build_stage_context(self) -> None:
        from alpha_quant.adapters.fake.canned_llm import CannedLLM
        from alpha_quant.domain.categories import module_from_component

        llm = CannedLLM()
        svc = ExplanationService(llm)
        comp = ScorecardComponent(
            name="technical_trend", category="technical", score=80.0, reason="Strong trend"
        )
        module = module_from_component(comp)
        sc = Scorecard(symbol="AAPL", recommendation=Recommendation.hold, total_score=65.0)
        ctx = svc._build_stage_context(comp, module, sc)
        assert ctx["id"] == "M3"
        assert ctx["score"] == 80.0
        assert ctx["symbol"] == "AAPL"
        assert ctx["total_score"] == 65.0

    def test_build_scorecard_context(self) -> None:
        from alpha_quant.adapters.fake.canned_llm import CannedLLM

        llm = CannedLLM()
        svc = ExplanationService(llm)
        sc = Scorecard(
            symbol="AAPL",
            recommendation=Recommendation.hold,
            confidence=0.7,
            total_score=65.0,
            facts_hash="abc",
            config_hash="def",
            strategy_version="1.0",
            data_quality=ComponentState.pass_,
        )
        ctx = svc._build_scorecard_context(sc)
        assert ctx["symbol"] == "AAPL"
        assert ctx["total_score"] == 65.0
        assert ctx["recommendation"] == "hold"
        assert "stages" in ctx

    def test_build_risk_context(self) -> None:
        from alpha_quant.adapters.fake.canned_llm import CannedLLM

        llm = CannedLLM()
        svc = ExplanationService(llm)
        report = {
            "as_of": "2026-01-05T14:00:00",
            "limits": [
                {
                    "name": "Gross exposure",
                    "current": "84.5%",
                    "limit": "90.0%",
                    "utilization": 0.94,
                    "breach": False,
                },
            ],
            "decisions": [
                {"action": "allow", "reason": "All limits within policy", "limit_name": ""}
            ],
            "posture": {"state": "ready", "text": "All limits within policy"},
            "headline": {"var_1d_99_pct": "3.2%", "var_1d_99_usd": "$11,200"},
            "var": {"levels": {"p95": {"pct": "1.8%", "usd": "$6,300"}}},
            "concentration": {"effective_bets": 5.2, "hhi": 0.22},
        }
        ctx = svc._build_risk_context(report)
        assert ctx["as_of"] == "2026-01-05T14:00:00"
        assert len(ctx["limits"]) == 1
        assert ctx["posture"]["state"] == "ready"
        assert "var_levels" in ctx
        assert "decisions" in ctx


class TestFakeStoreExplanationMethods:
    """Tests for FakeOperationalStore explanation lifecycle methods."""

    def test_save_and_load_advice_artifacts(self) -> None:
        from alpha_quant.adapters.fake.operational_store import FakeOperationalStore
        from alpha_quant.domain.advice import AdviceArtifact, AdviceRecommendation

        store = FakeOperationalStore()
        artifact = AdviceArtifact(
            scorecard_id="sc-1",
            scope="scorecard_stage",
            scope_id="M3",
            snapshot_id="snap-1",
            recommendation=AdviceRecommendation(
                headline="Test explanation",
                summary="Test summary",
                interpretation="Test interpretation",
            ),
        )
        aid = store.save_advice_artifact(artifact)
        assert aid != ""

        loaded = store.load_advice_artifacts(scope="scorecard_stage")
        assert len(loaded) == 1
        assert loaded[0].scope_id == "M3"
        assert loaded[0].recommendation.headline == "Test explanation"

    def test_mark_explanations_stale_by_scope(self) -> None:
        from alpha_quant.adapters.fake.operational_store import FakeOperationalStore
        from alpha_quant.domain.advice import AdviceArtifact

        store = FakeOperationalStore()
        store.save_advice_artifact(
            AdviceArtifact(scorecard_id="sc-1", scope="scorecard_stage", scope_id="M1")
        )
        store.save_advice_artifact(
            AdviceArtifact(scorecard_id="sc-1", scope="scorecard_stage", scope_id="M2")
        )
        store.save_advice_artifact(AdviceArtifact(scorecard_id="sc-1", scope="scorecard_overall"))

        count = store.mark_explanations_stale(scope="scorecard_stage")
        assert count == 2

        stage = store.load_advice_artifacts(scope="scorecard_stage")
        assert all(a.stale for a in stage)

        overall = store.load_advice_artifacts(scope="scorecard_overall")
        assert not any(a.stale for a in overall)

    def test_mark_explanations_stale_by_scorecard_id(self) -> None:
        from alpha_quant.adapters.fake.operational_store import FakeOperationalStore
        from alpha_quant.domain.advice import AdviceArtifact

        store = FakeOperationalStore()
        store.save_advice_artifact(
            AdviceArtifact(scorecard_id="sc-1", scope="scorecard_stage", scope_id="M1")
        )
        store.save_advice_artifact(
            AdviceArtifact(scorecard_id="sc-2", scope="scorecard_stage", scope_id="M1")
        )

        count = store.mark_explanations_stale(scope="scorecard_stage", scorecard_id="sc-1")
        assert count == 1

        sc1 = store.load_advice_artifacts(scope="scorecard_stage", scope_id="M1")
        sc1_stale = [a for a in sc1 if a.scorecard_id == "sc-1"]
        sc2_stale = [a for a in sc1 if a.scorecard_id == "sc-2"]
        assert all(a.stale for a in sc1_stale)
        assert not any(a.stale for a in sc2_stale)

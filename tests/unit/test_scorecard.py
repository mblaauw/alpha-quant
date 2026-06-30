from __future__ import annotations

from datetime import UTC, datetime

from alpha_quant.domain.advice import (
    AdviceAction,
    AdviceArtifact,
    AdviceRecommendation,
    OperatorOverride,
)
from alpha_quant.domain.scorecard import (
    ComponentState,
    Recommendation,
    Scorecard,
    ScorecardComponent,
    ScorecardEvidence,
)


class TestRecommendation:
    def test_values(self) -> None:
        assert Recommendation.watch.value == "watch"
        assert Recommendation.consider_entry.value == "consider_entry"
        assert Recommendation.hold.value == "hold"
        assert Recommendation.add.value == "add"
        assert Recommendation.reduce.value == "reduce"
        assert Recommendation.exit_.value == "exit"
        assert Recommendation.do_nothing.value == "do_nothing"


class TestComponentState:
    def test_values(self) -> None:
        assert ComponentState.pass_.value == "pass"
        assert ComponentState.warn.value == "warn"
        assert ComponentState.fail.value == "fail"


class TestScorecardComponent:
    def test_defaults(self) -> None:
        c = ScorecardComponent(name="momentum", category="technical")
        assert c.score == 0.0
        assert c.state == ComponentState.pass_
        assert c.weight == 1.0
        assert c.passed is True
        assert c.reason == ""
        assert c.details_json == "{}"

    def test_custom(self) -> None:
        c = ScorecardComponent(
            name="rsi_14",
            category="momentum",
            score=72.5,
            state=ComponentState.warn,
            weight=0.8,
            passed=False,
            reason="RSI above 70",
            details_json='{"value": 72.5}',
        )
        assert c.name == "rsi_14"
        assert c.score == 72.5
        assert c.state == ComponentState.warn
        assert c.passed is False
        assert c.reason == "RSI above 70"


class TestScorecard:
    def test_defaults(self) -> None:
        s = Scorecard()
        assert s.symbol == ""
        assert s.recommendation == Recommendation.do_nothing
        assert s.confidence == 0.0
        assert s.total_score == 0.0
        assert s.data_quality == ComponentState.pass_
        assert s.components == []

    def test_with_components(self) -> None:
        as_of = datetime(2026, 6, 27, 12, 0, 0, tzinfo=UTC)
        s = Scorecard(
            scorecard_id="sc-001",
            decision_run_id="run-001",
            portfolio_book_id="book-001",
            symbol="AAPL",
            security_id="sec-001",
            as_of=as_of,
            recommendation=Recommendation.hold,
            confidence=0.7,
            total_score=65.0,
            components=[
                ScorecardComponent(name="trend", category="technical", score=80.0, weight=0.5),
                ScorecardComponent(
                    name="valuation", category="fundamental", score=50.0, weight=0.5
                ),
            ],
        )
        assert s.symbol == "AAPL"
        assert s.recommendation == Recommendation.hold
        assert s.confidence == 0.7
        assert s.total_score == 65.0
        assert len(s.components) == 2
        assert s.components[0].score == 80.0
        assert s.components[1].score == 50.0

    def test_confidence_bounds(self) -> None:
        s = Scorecard(confidence=0.5)
        assert 0.0 <= s.confidence <= 1.0

    def test_total_score_bounds(self) -> None:
        s = Scorecard(total_score=50.0)
        assert 0.0 <= s.total_score <= 100.0


class TestScorecardEvidence:
    def test_defaults(self) -> None:
        e = ScorecardEvidence()
        assert e.source_type == ""
        assert e.source_id == ""
        assert e.value_json == "{}"

    def test_custom(self) -> None:
        e = ScorecardEvidence(
            source_type="readout",
            source_id="rsi_14",
            description="RSI (14) value",
            value_json='{"value": 65.2}',
        )
        assert e.source_type == "readout"
        assert e.source_id == "rsi_14"


class TestAdviceRecommendation:
    def test_defaults(self) -> None:
        r = AdviceRecommendation()
        assert r.recommendation == Recommendation.do_nothing
        assert r.key_reasons == []
        assert r.main_risks == []

    def test_custom(self) -> None:
        r = AdviceRecommendation(
            recommendation=Recommendation.hold,
            confidence_label="high",
            headline="AAPL: Hold",
            summary="Strong fundamentals",
            key_reasons=["Good PE ratio", "Strong revenue growth"],
            main_risks=["Valuation extended"],
            what_changed=["EPS beat estimates"],
        )
        assert r.recommendation == Recommendation.hold
        assert r.confidence_label == "high"
        assert len(r.key_reasons) == 2


class TestAdviceArtifact:
    def test_defaults(self) -> None:
        a = AdviceArtifact()
        assert a.advice_id == ""
        assert a.recommendation.recommendation == Recommendation.do_nothing
        assert a.deterministic_differs is False

    def test_with_recommendation(self) -> None:
        a = AdviceArtifact(
            advice_id="adv-001",
            scorecard_id="sc-001",
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            prompt_version="1.0",
            input_hash="abc123",
            output_hash="def456",
            validation_status="unverified",
            recommendation=AdviceRecommendation(
                recommendation=Recommendation.add,
                confidence_label="medium",
                headline="Add AAPL",
                summary="Technical setup improving",
            ),
            deterministic_differs=False,
        )
        assert a.advice_id == "adv-001"
        assert a.recommendation.headline == "Add AAPL"
        assert a.recommendation.recommendation == Recommendation.add
        assert a.deterministic_differs is False


class TestOperatorOverride:
    def test_defaults(self) -> None:
        o = OperatorOverride()
        assert o.override_action == AdviceAction.follow
        assert o.original_recommendation == Recommendation.do_nothing
        assert o.modified_recommendation is None

    def test_reject(self) -> None:
        o = OperatorOverride(
            override_id="ov-001",
            scorecard_id="sc-001",
            command_id="cmd-001",
            actor_id="user-001",
            original_recommendation=Recommendation.add,
            original_confidence=0.8,
            override_action=AdviceAction.reject,
            reason="Market conditions changed",
        )
        assert o.override_action == AdviceAction.reject
        assert o.original_recommendation == Recommendation.add
        assert o.reason == "Market conditions changed"

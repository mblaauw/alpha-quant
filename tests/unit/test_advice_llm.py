from __future__ import annotations

from alpha_quant.application.advice_llm import AdviceLLMService, PortfolioSummary
from alpha_quant.domain.scorecard import Recommendation, Scorecard


class TestAdviceLLMService:
    def test_class_exists(self) -> None:
        assert AdviceLLMService is not None

    def test_fallback_recommendation(self) -> None:
        from alpha_quant.adapters.fake.canned_llm import CannedLLM

        llm = CannedLLM()
        svc = AdviceLLMService(llm)
        rec = svc._fallback_recommendation(Recommendation.hold)
        assert rec.recommendation == Recommendation.hold
        assert rec.confidence_label == "low"
        assert "Deterministic" in rec.headline

    def test_parse_valid_json(self) -> None:
        from alpha_quant.adapters.fake.canned_llm import CannedLLM

        llm = CannedLLM()
        svc = AdviceLLMService(llm)
        raw = (
            '{"headline": "Hold AAPL", "recommended_action": "hold",'
            ' "confidence_label": "medium", "summary": "Test",'
            ' "key_reasons": ["a"], "main_risks": ["b"]}'
        )
        result = svc._parse_llm_response(raw)
        assert result is not None
        assert result.recommendation == Recommendation.hold
        assert result.headline == "Hold AAPL"

    def test_parse_with_markdown_fence(self) -> None:
        from alpha_quant.adapters.fake.canned_llm import CannedLLM

        raw = (
            '```json\n{"headline": "Test", "recommended_action": "do_nothing",'
            ' "confidence_label": "low", "summary": "x"}\n```'
        )
        llm = CannedLLM()
        svc = AdviceLLMService(llm)
        result = svc._parse_llm_response(raw)
        assert result is not None
        assert result.recommendation == Recommendation.do_nothing

    def test_parse_invalid_json_returns_none(self) -> None:
        from alpha_quant.adapters.fake.canned_llm import CannedLLM

        llm = CannedLLM()
        svc = AdviceLLMService(llm)
        result = svc._parse_llm_response("not json")
        assert result is None

    def test_parse_missing_field_defaults(self) -> None:
        from alpha_quant.adapters.fake.canned_llm import CannedLLM

        llm = CannedLLM()
        svc = AdviceLLMService(llm)
        raw = '{"headline": "Test"}'
        result = svc._parse_llm_response(raw)
        assert result is not None
        assert result.key_reasons == []

    def test_build_scorecard_dict(self) -> None:
        from alpha_quant.adapters.fake.canned_llm import CannedLLM

        llm = CannedLLM()
        svc = AdviceLLMService(llm)
        sc = Scorecard(
            symbol="AAPL", recommendation=Recommendation.hold, confidence=0.7, total_score=65.0
        )
        d = svc._build_scorecard_dict(sc)
        assert d["symbol"] == "AAPL"
        assert d["recommendation"] == "hold"
        assert d["total_score"] == 65.0
        assert "components" in d

    def test_generate_advice_with_canned_llm(self) -> None:
        from alpha_quant.adapters.fake.canned_llm import CannedLLM

        llm = CannedLLM("No explanation available.")
        svc = AdviceLLMService(llm)
        sc = Scorecard(
            symbol="AAPL", recommendation=Recommendation.hold, confidence=0.7, total_score=65.0
        )
        artifact = svc.generate_advice(sc)
        assert artifact.scorecard_id == ""
        assert artifact.llm_provider == ""
        assert artifact.input_hash != ""
        assert artifact.output_hash != ""
        assert artifact.validation_status == "failed"
        assert artifact.recommendation.recommendation == Recommendation.hold
        assert artifact.deterministic_differs is False

    def test_generate_advice_has_hashes(self) -> None:
        from alpha_quant.adapters.fake.canned_llm import CannedLLM

        llm = CannedLLM()
        svc = AdviceLLMService(llm)
        sc = Scorecard(
            symbol="AAPL",
            recommendation=Recommendation.add,
            confidence=0.8,
            total_score=80.0,
        )
        artifact = svc.generate_advice(sc)
        assert artifact.input_hash != ""
        assert artifact.output_hash != ""
        assert artifact.validation_status == "verified"

    def test_portfolio_summary_defaults(self) -> None:
        p = PortfolioSummary()
        assert p.equity == 0.0
        assert p.cash == 0.0
        assert p.position_count == 0
        assert p.regime == "RISK_ON"

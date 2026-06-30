from __future__ import annotations

from datetime import UTC, datetime

from alpha_quant.application.scorecards import (
    PortfolioContext,
    PositionContext,
    _compute_total_score,
    _recommendation_from_score,
    _score_attention_crowding,
    _score_data_quality,
    _score_event_risk,
    _score_fundamentals,
    _score_insider_activity,
    _score_momentum,
    _score_participation,
    _score_portfolio_fit,
    _score_relative_strength,
    _score_technical_trend,
    _score_volatility,
    generate_scorecards,
)
from alpha_quant.contracts.alpha_lake import (
    FactsBundle,
    FactsBundleMetadata,
    FactsBundleSections,
    FundamentalMetric,
    InsiderTransaction,
    MentionObservation,
    ReadoutDefinition,
    ReadoutItem,
    ReadoutObservation,
)
from alpha_quant.domain.scorecard import ComponentState, Recommendation


def _make_bundle(
    symbol: str = "AAPL",
    readouts: list[ReadoutItem] | None = None,
    fundamentals: list[FundamentalMetric] | None = None,
    insider: list[InsiderTransaction] | None = None,
    earnings: list | None = None,
    mentions: list[MentionObservation] | None = None,
) -> FactsBundle:
    return FactsBundle(
        metadata=FactsBundleMetadata(
            symbol=symbol,
            as_of=datetime(2026, 6, 27, 12, 0, 0, tzinfo=UTC),
        ),
        sections=FactsBundleSections(
            readouts=readouts or [],
            fundamentals=fundamentals or [],
            insider_transactions=insider or [],
            earnings_events=earnings or [],
            attention_mentions=mentions or [],
        ),
    )


def _r(readout_id: str, value: float) -> ReadoutItem:
    return ReadoutItem(
        definition=ReadoutDefinition(
            readout_id=readout_id,
            label=readout_id,
            category="test",
        ),
        observations=[ReadoutObservation(effective_date="2026-06-26", value=value)],
    )


class TestTechnicalTrend:
    def test_strong_trend(self) -> None:
        bundle = _make_bundle(readouts=[_r("trend.regime", 45), _r("trend.directional_bias", 20)])
        c = _score_technical_trend(bundle)
        assert c.score >= 60

    def test_downward_bias(self) -> None:
        bundle = _make_bundle(readouts=[_r("trend.regime", 30), _r("trend.directional_bias", -15)])
        c = _score_technical_trend(bundle)
        assert c.score <= 50

    def test_missing_data(self) -> None:
        bundle = _make_bundle(readouts=[])
        c = _score_technical_trend(bundle)
        assert c.score > 0


class TestMomentum:
    def test_strong_momentum(self) -> None:
        bundle = _make_bundle(readouts=[_r("momentum.macd_cross", 2.0), _r("momentum.rsi_14", 55)])
        c = _score_momentum(bundle)
        assert c.score >= 60

    def test_overbought_rsi_reduces(self) -> None:
        bundle = _make_bundle(readouts=[_r("momentum.macd_cross", 1.0), _r("momentum.rsi_14", 75)])
        c = _score_momentum(bundle)
        assert c.state == ComponentState.warn

    def test_missing_data(self) -> None:
        bundle = _make_bundle(readouts=[])
        c = _score_momentum(bundle)
        assert c.score > 0


class TestVolatility:
    def test_low_volatility(self) -> None:
        bundle = _make_bundle(readouts=[_r("atr_pct_14", 0.01)])
        c = _score_volatility(bundle)
        assert c.score >= 80

    def test_high_volatility(self) -> None:
        bundle = _make_bundle(readouts=[_r("atr_pct_14", 0.05)])
        c = _score_volatility(bundle)
        assert c.score <= 20

    def test_missing_data(self) -> None:
        bundle = _make_bundle(readouts=[])
        c = _score_volatility(bundle)
        assert c.score == 50.0


class TestParticipation:
    def test_healthy_volume(self) -> None:
        bundle = _make_bundle(readouts=[_r("volume_ratio_21", 1.0)])
        c = _score_participation(bundle)
        assert c.score >= 70

    def test_abnormal_volume(self) -> None:
        bundle = _make_bundle(readouts=[_r("volume_ratio_21", 3.0)])
        c = _score_participation(bundle)
        assert c.state == ComponentState.warn

    def test_low_volume(self) -> None:
        bundle = _make_bundle(readouts=[_r("volume_ratio_21", 0.3)])
        c = _score_participation(bundle)
        assert c.score <= 40


class TestRelativeStrength:
    def test_outperforming(self) -> None:
        bundle = _make_bundle(readouts=[_r("relative_strength.vs_benchmark", 0.08)])
        c = _score_relative_strength(bundle, None)
        assert c.score >= 60

    def test_underperforming(self) -> None:
        bundle = _make_bundle(readouts=[_r("relative_strength.vs_benchmark", -0.08)])
        c = _score_relative_strength(bundle, None)
        assert c.score <= 40

    def test_no_spy_data(self) -> None:
        bundle = _make_bundle(readouts=[])
        c = _score_relative_strength(bundle, None)
        assert c.score > 0


class TestFundamentals:
    def test_passes(self) -> None:
        bundle = _make_bundle(
            fundamentals=[
                FundamentalMetric(metric_id="pe_ttm", name="PE", category="valuation", value=20.0),
            ]
        )
        c = _score_fundamentals(bundle)
        assert c.passed is True
        assert c.score >= 60

    def test_high_pe_fails(self) -> None:
        bundle = _make_bundle(
            fundamentals=[
                FundamentalMetric(metric_id="pe_ttm", name="PE", category="valuation", value=150.0),
            ]
        )
        c = _score_fundamentals(bundle)
        assert c.passed is False

    def test_no_data(self) -> None:
        bundle = _make_bundle(fundamentals=[])
        c = _score_fundamentals(bundle)
        assert c.score >= 0


class TestEventRisk:
    def test_no_event(self) -> None:
        bundle = _make_bundle(earnings=[])
        c = _score_event_risk(bundle, datetime(2026, 6, 27).date())
        assert c.score >= 80

    def test_in_blackout(self) -> None:
        bundle = _make_bundle(earnings=[type("E", (), {"effective_date": "2026-07-01"})()])
        c = _score_event_risk(bundle, datetime(2026, 6, 27).date())
        assert c.score <= 20

    def test_recent_earnings(self) -> None:
        bundle = _make_bundle(earnings=[type("E", (), {"effective_date": "2026-06-26"})()])
        c = _score_event_risk(bundle, datetime(2026, 6, 27).date())
        assert c.score == 40.0


class TestInsiderActivity:
    def test_no_insider_data(self) -> None:
        bundle = _make_bundle(insider=[])
        c = _score_insider_activity(bundle)
        assert c.score == 50.0

    def test_net_buying(self) -> None:
        bundle = _make_bundle(
            insider=[
                InsiderTransaction(effective_date="2026-06-26", transaction_type="Buy", shares=100),
                InsiderTransaction(effective_date="2026-06-26", transaction_type="Buy", shares=50),
            ]
        )
        c = _score_insider_activity(bundle)
        assert c.score >= 60

    def test_net_selling(self) -> None:
        bundle = _make_bundle(
            insider=[
                InsiderTransaction(
                    effective_date="2026-06-26", transaction_type="Sell", shares=100
                ),
            ]
        )
        c = _score_insider_activity(bundle)
        assert c.score <= 30


class TestAttentionCrowding:
    def test_low_attention(self) -> None:
        bundle = _make_bundle(mentions=[])
        c = _score_attention_crowding(bundle)
        assert c.score >= 70

    def test_extreme_spike(self) -> None:
        bundle = _make_bundle(
            mentions=[
                MentionObservation(effective_date="2026-06-20", count=5),
                MentionObservation(effective_date="2026-06-21", count=5),
                MentionObservation(effective_date="2026-06-22", count=5),
                MentionObservation(effective_date="2026-06-23", count=5),
                MentionObservation(effective_date="2026-06-24", count=5),
                MentionObservation(effective_date="2026-06-25", count=5),
                MentionObservation(effective_date="2026-06-26", count=500),
            ]
        )
        c = _score_attention_crowding(bundle)
        assert c.state == ComponentState.warn


class TestPortfolioFit:
    def test_empty_portfolio(self) -> None:
        portfolio = PortfolioContext(equity=100000, cash=50000, max_positions=10)
        c = _score_portfolio_fit("AAPL", portfolio)
        assert c.score >= 70

    def test_portfolio_full(self) -> None:
        portfolio = PortfolioContext(
            equity=100000,
            cash=50000,
            max_positions=3,
            positions={
                "MSFT": PositionContext(),
                "GOOG": PositionContext(),
                "AMZN": PositionContext(),
            },
        )
        c = _score_portfolio_fit("AAPL", portfolio)
        assert c.score <= 30

    def test_overweight(self) -> None:
        portfolio = PortfolioContext(
            equity=100000,
            cash=50000,
            positions={"AAPL": PositionContext(symbol="AAPL", market_value=40000)},
        )
        c = _score_portfolio_fit("AAPL", portfolio)
        assert c.state == ComponentState.warn


class TestScoreDataQuality:
    def test_good_data(self) -> None:
        bundle = _make_bundle(
            readouts=[
                _r("price.last", 100),
                _r("momentum.rsi_14", 50),
                _r("momentum.macd_cross", 0.5),
                _r("participation.rvol", 1.0),
                _r("volatility.atr_percent", 0.02),
                _r("volatility.bollinger_width", 0.1),
            ]
        )
        c = _score_data_quality(bundle)
        assert c.state == ComponentState.pass_

    def test_poor_data(self) -> None:
        bundle = _make_bundle(readouts=[_r("price.last", 100)])
        c = _score_data_quality(bundle)
        assert c.state == ComponentState.fail


class TestRecommendationFromScore:
    def test_high_score_add(self) -> None:
        r = _recommendation_from_score(85.0, True, {})
        assert r == Recommendation.add

    def test_high_score_consider_entry(self) -> None:
        r = _recommendation_from_score(85.0, False, {})
        assert r == Recommendation.consider_entry

    def test_medium_score_hold(self) -> None:
        r = _recommendation_from_score(65.0, True, {})
        assert r == Recommendation.hold

    def test_low_score_reduce(self) -> None:
        r = _recommendation_from_score(20.0, True, {})
        assert r == Recommendation.reduce

    def test_low_score_do_nothing(self) -> None:
        r = _recommendation_from_score(20.0, False, {})
        assert r == Recommendation.do_nothing


class TestComputeTotalScore:
    def test_weighted_average(self) -> None:
        from alpha_quant.domain.scorecard import ScorecardComponent

        components = [
            ScorecardComponent(name="a", category="x", score=100.0, weight=0.5),
            ScorecardComponent(name="b", category="x", score=0.0, weight=0.5),
        ]
        score = _compute_total_score(components, "RISK_ON")
        assert score == 50.0

    def test_regime_caution_reduces(self) -> None:
        from alpha_quant.domain.scorecard import ScorecardComponent

        components = [
            ScorecardComponent(name="a", category="x", score=100.0, weight=1.0),
        ]
        score = _compute_total_score(components, "CAUTION")
        assert score == 60.0

    def test_regime_off_drastic(self) -> None:
        from alpha_quant.domain.scorecard import ScorecardComponent

        components = [
            ScorecardComponent(name="a", category="x", score=100.0, weight=1.0),
        ]
        score = _compute_total_score(components, "RISK_OFF")
        assert score == 20.0


class TestGenerateScorecards:
    def test_empty_bundles(self) -> None:
        portfolio = PortfolioContext(equity=100000, cash=50000)
        result = generate_scorecards({}, portfolio, strategy_version_id="sv-1")
        assert result == []

    def test_single_symbol(self) -> None:
        bundle = _make_bundle(
            "AAPL",
            readouts=[
                _r("close", 110),
                _r("sma_50", 100),
                _r("rsi_14", 55),
                _r("return_63d", 0.15),
                _r("volume_ratio_21", 1.0),
                _r("atr_pct_14", 0.02),
            ],
        )
        portfolio = PortfolioContext(equity=100000, cash=50000)
        result = generate_scorecards({"AAPL": bundle}, portfolio, strategy_version_id="sv-1")
        assert len(result) == 1
        assert result[0].symbol == "AAPL"
        assert result[0].total_score > 0
        assert len(result[0].components) == 13
        assert result[0].config_hash != ""
        assert result[0].strategy_version == "sv-1"
        assert result[0].facts_hash != ""

    def test_spy_excluded(self) -> None:
        spy = _make_bundle("SPY", readouts=[_r("close", 100), _r("sma_50", 100)])
        aapl = _make_bundle("AAPL", readouts=[_r("close", 110), _r("sma_50", 100)])
        portfolio = PortfolioContext(equity=100000, cash=50000)
        result = generate_scorecards(
            {"AAPL": aapl, "SPY": spy}, portfolio, spy_bundle=spy, strategy_version_id="sv-1"
        )
        symbols = {s.symbol for s in result}
        assert "SPY" not in symbols
        assert "AAPL" in symbols

    def test_data_quality_fail_blocks(self) -> None:
        bundle = _make_bundle("AAPL", readouts=[_r("close", 100)])
        portfolio = PortfolioContext(equity=100000, cash=50000)
        result = generate_scorecards({"AAPL": bundle}, portfolio, strategy_version_id="sv-1")
        assert len(result) == 1
        assert result[0].recommendation == Recommendation.do_nothing

    def test_facts_hash_includes_sections(self) -> None:
        from alpha_quant.contracts.alpha_lake import (
            EarningsEvent,
            InsiderTransaction,
            MentionObservation,
        )

        bundle = _make_bundle(
            "AAPL",
            readouts=[_r("close", 110), _r("sma_50", 100)],
            insider=[
                InsiderTransaction(effective_date="2026-06-25", transaction_type="Buy", shares=1000)
            ],
            earnings=[EarningsEvent(effective_date="2026-07-15", symbol="AAPL")],
            mentions=[MentionObservation(effective_date="2026-06-26", count=50)],
        )
        bundle_no_extra = _make_bundle(
            "AAPL",
            readouts=[_r("close", 110), _r("sma_50", 100)],
        )
        portfolio = PortfolioContext(equity=100000, cash=50000)
        result1 = generate_scorecards({"AAPL": bundle}, portfolio, strategy_version_id="sv-1")
        result2 = generate_scorecards(
            {"AAPL": bundle_no_extra}, portfolio, strategy_version_id="sv-1"
        )
        assert result1[0].facts_hash != result2[0].facts_hash

    def test_config_hash_stable(self) -> None:
        bundle = _make_bundle("AAPL", readouts=[_r("close", 110), _r("sma_50", 100)])
        portfolio = PortfolioContext(equity=100000, cash=50000)
        result1 = generate_scorecards({"AAPL": bundle}, portfolio, strategy_version_id="sv-1")
        result2 = generate_scorecards({"AAPL": bundle}, portfolio, strategy_version_id="sv-1")
        assert result1[0].config_hash == result2[0].config_hash


class TestScorecardProperties:
    """Property-based invariants for scorecard engine."""

    def test_scores_in_range(self) -> None:
        """All component scores must be ∈ [0, 100]."""
        bundle = _make_bundle("AAPL", readouts=[_r("close", 110), _r("sma_50", 100)])
        portfolio = PortfolioContext(equity=100000, cash=50000, regime="RISK_ON")
        result = generate_scorecards({"AAPL": bundle}, portfolio, strategy_version_id="sv-1")[0]
        for comp in result.components:
            assert 0.0 <= comp.score <= 100.0, f"{comp.name} score {comp.score} ∉ [0, 100]"

    def test_scores_in_range_risk_off(self) -> None:
        """All component scores still ∈ [0, 100] under RISK_OFF."""
        bundle = _make_bundle("AAPL", readouts=[_r("close", 110), _r("sma_50", 100)])
        portfolio = PortfolioContext(equity=100000, cash=50000, regime="RISK_OFF")
        result = generate_scorecards({"AAPL": bundle}, portfolio, strategy_version_id="sv-1")[0]
        for comp in result.components:
            assert 0.0 <= comp.score <= 100.0, f"{comp.name} score {comp.score} ∉ [0, 100]"

    def test_risk_off_lowers_scores(self) -> None:
        """RISK_OFF scores must be ≤ same-input RISK_ON scores."""
        bundle = _make_bundle("AAPL", readouts=[_r("close", 110), _r("sma_50", 100)])
        on_result = generate_scorecards(
            {"AAPL": bundle},
            PortfolioContext(equity=100000, cash=50000, regime="RISK_ON"),
            strategy_version_id="sv-1",
        )[0]
        off_result = generate_scorecards(
            {"AAPL": bundle},
            PortfolioContext(equity=100000, cash=50000, regime="RISK_OFF"),
            strategy_version_id="sv-1",
        )[0]
        on_scores = {c.name: c.score for c in on_result.components}
        off_scores = {c.name: c.score for c in off_result.components}
        for name in on_scores:
            assert off_scores[name] <= on_scores[name], (
                f"{name} RISK_OFF ({off_scores[name]}) > RISK_ON ({on_scores[name]})"
            )

    def test_total_score_non_negative(self) -> None:
        """Total score must be ≥ 0."""
        bundle = _make_bundle("AAPL", readouts=[_r("close", 110), _r("sma_50", 100)])
        portfolio = PortfolioContext(equity=100000, cash=50000)
        result = generate_scorecards({"AAPL": bundle}, portfolio, strategy_version_id="sv-1")[0]
        assert result.total_score >= 0

    def test_config_hash_deterministic(self) -> None:
        """Same inputs produce same config_hash."""
        bundle = _make_bundle("AAPL", readouts=[_r("close", 110), _r("sma_50", 100)])
        portfolio = PortfolioContext(equity=100000, cash=50000)
        r1 = generate_scorecards({"AAPL": bundle}, portfolio, strategy_version_id="sv-1")[0]
        r2 = generate_scorecards({"AAPL": bundle}, portfolio, strategy_version_id="sv-1")[0]
        assert r1.config_hash == r2.config_hash

"""Performance benchmarks for hot paths (scoring, ranking)."""

from datetime import date, timedelta

from domain.models import Bar, Candidate, IndicatorState
from domain.ranking import rank
from domain.technical import score


def _make_bars(count: int) -> list[Bar]:
    base = date(2025, 1, 1)
    return [
        Bar(
            symbol="SPY",
            date=base + timedelta(days=i),
            open=100.0 + i * 0.1,
            high=101.0 + i * 0.1,
            low=99.0 + i * 0.1,
            close=100.5 + i * 0.1,
            volume=1_000_000,
        )
        for i in range(count)
    ]


def _make_indicator() -> IndicatorState:
    return IndicatorState(
        symbol="SPY",
        date=date(2026, 6, 11),
        values={
            "processed_close": 100.0,
            "ema12": 101.0,
            "ema20": 100.5,
            "ema50": 99.0,
            "ema200": 95.0,
            "rsi": 55.0,
            "atr": 2.0,
            "macd": 1.0,
            "macd_signal": 0.5,
            "macd_histogram": 0.5,
        },
        status="ok",
    )


def _make_candidate(symbol: str) -> Candidate:
    return Candidate(
        symbol=symbol,
        date=date(2026, 6, 11),
        scores={"technical": 0.7, "momentum": 0.5},
        composite_score=0.6,
        regime="RISK_ON",
        gate_results={"m1": True, "m4": True},
    )


class TestScoringBenchmark:
    def test_scoring_500_candidates_completes(self) -> None:
        bars = _make_bars(400)
        state = _make_indicator()
        for _ in range(500):
            score(bars, state)


class TestRankingBenchmark:
    def test_ranking_500_candidates_completes(self) -> None:
        candidates = [_make_candidate(f"SYM{i:04d}") for i in range(500)]
        result = rank(candidates, max_positions=50, current_count=0)
        assert len(result) == 50

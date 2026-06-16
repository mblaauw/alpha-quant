"""Unit tests for M3 technical score (domain.technical)."""

from datetime import date

from domain.models import Bar, IndicatorState
from domain.technical import TechnicalScore, momentum_score, score


def _bar(close: float, volume: float = 1_000_000) -> Bar:
    return Bar(
        symbol="AAPL",
        date=date(2026, 6, 11),
        open=close * 0.99,
        high=close * 1.01,
        low=close * 0.99,
        close=close,
        volume=volume,
    )


def _state(**values: float) -> IndicatorState:
    return IndicatorState(
        symbol="AAPL",
        date=date(2026, 6, 11),
        values=dict(values),
    )


class TestScore:
    def test_returns_technical_score(self) -> None:
        bars = [_bar(100)] * 64
        state = _state(processed_close=100, ema50=95, rsi=55, macd_histogram=0.5, atr=1.0)
        result = score(bars, state)
        assert isinstance(result, TechnicalScore)

    def test_zero_score_when_close_missing(self) -> None:
        bars = [_bar(100)]
        state = _state()
        result = score(bars, state)
        assert result.score == 0.0

    def test_zero_score_when_close_is_nan(self) -> None:
        bars = [_bar(100)]
        state = _state(processed_close=float("nan"))
        result = score(bars, state)
        assert result.score == 0.0

    def test_score_between_0_and_1(self) -> None:
        bars = [_bar(100)] * 64
        state = _state(processed_close=100, ema50=95, rsi=55, macd_histogram=0.5, atr=1.0)
        for _ in range(10):
            result = score(bars, state)
            assert 0.0 <= result.score <= 1.0


class TestMomentumScore:
    def test_high_momentum(self) -> None:
        bars = [_bar(100)] * 63 + [_bar(130)]
        result = momentum_score(bars, 130)
        assert result == 1.0

    def test_moderate_momentum(self) -> None:
        bars = [_bar(100)] * 63 + [_bar(115)]
        result = momentum_score(bars, 115)
        assert result == 0.8

    def test_positive_momentum(self) -> None:
        bars = [_bar(100)] * 63 + [_bar(107)]
        result = momentum_score(bars, 107)
        assert result == 0.6

    def test_slightly_positive(self) -> None:
        bars = [_bar(100)] * 63 + [_bar(102)]
        result = momentum_score(bars, 102)
        assert result == 0.5

    def test_slightly_negative(self) -> None:
        bars = [_bar(100)] * 63 + [_bar(98)]
        result = momentum_score(bars, 98)
        assert result == 0.3

    def test_moderately_negative(self) -> None:
        bars = [_bar(100)] * 63 + [_bar(88)]
        result = momentum_score(bars, 88)
        assert result == 0.1

    def test_very_negative(self) -> None:
        bars = [_bar(100)] * 63 + [_bar(70)]
        result = momentum_score(bars, 70)
        assert result == 0.0

    def test_default_with_fewer_than_two_bars(self) -> None:
        result = momentum_score([_bar(100)], 100)
        assert result == 0.3

    def test_zero_with_negative_prev_close(self) -> None:
        bars = [
            Bar(
                symbol="AAPL",
                date=date(2026, 6, 9),
                open=1.0,
                high=2.0,
                low=0.0,
                close=0.5,
                volume=1_000_000,
            ),
            Bar(
                symbol="AAPL",
                date=date(2026, 6, 10),
                open=0.5,
                high=1.0,
                low=0.0,
                close=0.5,
                volume=1_000_000,
            ),
        ]
        result = momentum_score(bars, close=0.0)
        assert result == 0.0

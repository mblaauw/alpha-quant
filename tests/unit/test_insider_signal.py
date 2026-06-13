"""Unit tests for M5 insider cluster signal (alpha_quant.domain.insider_signal)."""

from datetime import date, timedelta

from alpha_quant.domain.insider_signal import InsiderVerdict, evaluate
from alpha_quant.domain.models import InsiderTransaction


def _tx(
    symbol: str = "AAPL",
    days_ago: int = 5,
    owner: str = "owner1",
    title: str = "CEO",
    tx_type: str = "Buy",
    shares: float = 10_000.0,
    price: float = 150.0,
) -> InsiderTransaction:
    return InsiderTransaction(
        symbol=symbol,
        transaction_date=date(2026, 6, 11) - timedelta(days=days_ago),
        owner=owner,
        title=title,
        transaction_type=tx_type,
        shares_traded=shares,
        price=price,
    )


class TestEvaluate:
    def test_no_transactions_returns_zero(self) -> None:
        result = evaluate("AAPL", [], as_of_date=date(2026, 6, 11))
        assert result.score == 0.0
        assert result.reason is not None

    def test_no_buy_transactions_without_csuite_sell(self) -> None:
        txns = [_tx(tx_type="Sell")]
        result = evaluate("AAPL", txns, as_of_date=date(2026, 6, 11))
        assert result.score == 0.0

    def test_transactions_outside_window_returns_zero(self) -> None:
        txns = [_tx(days_ago=60)]
        result = evaluate("AAPL", txns, as_of_date=date(2026, 6, 11))
        assert result.score == 0.0

    def test_future_transaction_excluded(self) -> None:
        txns = [_tx(days_ago=-5)]
        result = evaluate("AAPL", txns, as_of_date=date(2026, 6, 11))
        assert result.score == 0.0

    def test_single_officer_not_enough(self) -> None:
        txns = [_tx(owner="owner1", title="CEO", shares=100_000, price=200.0)]
        result = evaluate("AAPL", txns, as_of_date=date(2026, 6, 11))
        assert result.score == 0.0

    def test_two_officers_meets_cluster_threshold(self) -> None:
        txns = [
            _tx(owner="owner1", title="CEO", shares=10_000, price=150.0),
            _tx(owner="owner2", title="CFO", shares=5_000, price=150.0),
        ]
        result = evaluate("AAPL", txns, as_of_date=date(2026, 6, 11))
        assert result.score > 0.0
        assert "cluster" in (result.reason or "")

    def test_officer_and_director_meets_threshold(self) -> None:
        txns = [
            _tx(owner="owner1", title="CEO", shares=5_000, price=150.0),
            _tx(owner="owner2", title="Director", shares=5_000, price=150.0),
        ]
        result = evaluate("AAPL", txns, as_of_date=date(2026, 6, 11))
        assert result.score > 0.0

    def test_value_below_200k_returns_zero(self) -> None:
        txns = [
            _tx(owner="owner1", title="CEO", shares=100, price=100.0),
            _tx(owner="owner2", title="CFO", shares=100, price=100.0),
        ]
        result = evaluate("AAPL", txns, as_of_date=date(2026, 6, 11))
        assert result.score == 0.0

    def test_case_insensitive_symbol(self) -> None:
        txns = [
            _tx(symbol="aapl", owner="owner1", title="CEO", shares=10_000, price=150.0),
            _tx(symbol="AAPL", owner="owner2", title="CFO", shares=10_000, price=150.0),
        ]
        result = evaluate("AAPL", txns, as_of_date=date(2026, 6, 11))
        assert result.score > 0.0

    def test_ignores_other_symbols(self) -> None:
        txns = [
            _tx(symbol="MSFT", owner="owner1", title="CEO", shares=10_000, price=150.0),
            _tx(symbol="MSFT", owner="owner2", title="CFO", shares=10_000, price=150.0),
        ]
        result = evaluate("AAPL", txns, as_of_date=date(2026, 6, 11))
        assert result.score == 0.0

    def test_transaction_without_price_excluded(self) -> None:
        txns = [
            _tx(owner="owner1", title="CEO", shares=10_000, price=150.0),
            _tx(owner="owner2", title="CFO", shares=10_000, price=150.0),
            _tx(owner="owner3", title="Director", shares=5_000, price=None),
        ]
        result = evaluate("AAPL", txns, as_of_date=date(2026, 6, 11))
        assert result.score > 0.0

    def test_custom_lookback(self) -> None:
        txns = [
            _tx(owner="owner1", title="CEO", shares=10_000, price=150.0, days_ago=20),
            _tx(owner="owner2", title="CFO", shares=10_000, price=150.0, days_ago=20),
        ]
        result = evaluate("AAPL", txns, as_of_date=date(2026, 6, 11), lookback=15)
        assert result.score == 0.0

    def test_president_detected_as_officer(self) -> None:
        txns = [
            _tx(owner="owner1", title="President", shares=10_000, price=150.0),
            _tx(owner="owner2", title="VP", shares=10_000, price=150.0),
        ]
        result = evaluate("AAPL", txns, as_of_date=date(2026, 6, 11))
        assert result.score > 0.0

    def test_market_cap_scales_threshold(self) -> None:
        txns = [
            _tx(owner="owner1", title="CEO", shares=10_000, price=150.0),
            _tx(owner="owner2", title="CFO", shares=10_000, price=150.0),
        ]
        result_small = evaluate("AAPL", txns, as_of_date=date(2026, 6, 11), market_cap=10_000_000.0)
        result_large = evaluate(
            "AAPL", txns, as_of_date=date(2026, 6, 11), market_cap=1_000_000_000_000.0
        )  # noqa: E501
        assert result_small.score > 0.0
        assert result_large.score == 0.0

    def test_insider_verdict_default_reason(self) -> None:
        v = InsiderVerdict(score=0.0)
        assert v.score == 0.0
        assert v.reason is None

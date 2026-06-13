"""Unit tests for PaperPortfolio risk action handling."""

from datetime import date

from alpha_quant.app.paper import PaperPortfolio
from alpha_quant.domain.models import Bar, Position
from alpha_quant.domain.risk import RiskAction


class _FakeStore:
    def __init__(self) -> None:
        self._positions: list[Position] = []
        self.saved_positions: list[Position] = []

    def load_latest_portfolio_snapshot(self) -> None:
        return None

    def load_positions(self) -> list[Position]:
        return self._positions

    def save_position(self, pos: Position) -> None:
        self.saved_positions.append(pos)

    def save_event(self, event: object) -> None:
        pass

    def save_fill(self, fill: object) -> None:
        pass

    def transaction(self) -> object:
        class _Txn:
            def __enter__(self) -> object:  # noqa: N805
                return self

            def __exit__(self, *args: object) -> None:
                pass

        return _Txn()


def _bar() -> Bar:
    return Bar(
        symbol="AAPL",
        date=date(2026, 6, 11),
        open=100.0,
        high=105.0,
        low=95.0,
        close=100.0,
        volume=1_000_000,
    )


class TestPaperRiskActions:
    def test_drawdown_cut_reduces_positions(self) -> None:
        store = _FakeStore()
        store._positions = [
            Position(
                symbol="AAPL",
                quantity=100.0,
                avg_cost=100.0,
                entry_price=100.0,
                current_price=100.0,
                market_value=10_000.0,
            ),
            Position(
                symbol="MSFT",
                quantity=200.0,
                avg_cost=200.0,
                entry_price=200.0,
                current_price=200.0,
                market_value=40_000.0,
            ),
        ]
        portfolio = PaperPortfolio(store)
        actions = [
            RiskAction(action_type="drawdown_cut", symbol="", shares=0.0, reason="test", price=0.5)
        ]
        result = portfolio.process_risk_actions(actions, _bar())
        assert len(result.violations) == 0
        aapl = next(p for p in store.saved_positions if p.symbol == "AAPL")
        msft = next(p for p in store.saved_positions if p.symbol == "MSFT")
        assert aapl.quantity == 50.0
        assert msft.quantity == 100.0

    def test_drawdown_cut_zero_closes_positions(self) -> None:
        store = _FakeStore()
        store._positions = [
            Position(
                symbol="AAPL",
                quantity=100.0,
                avg_cost=100.0,
                entry_price=100.0,
                current_price=100.0,
                market_value=10_000.0,
            ),
        ]
        portfolio = PaperPortfolio(store)
        actions = [
            RiskAction(action_type="drawdown_cut", symbol="", shares=0.0, reason="test", price=0.0)
        ]
        result = portfolio.process_risk_actions(actions, _bar())
        assert len(result.violations) == 0
        aapl = next(p for p in store.saved_positions if p.symbol == "AAPL")
        assert aapl.quantity == 0.0

    def test_daily_halt_closes_all_positions(self) -> None:
        store = _FakeStore()
        store._positions = [
            Position(
                symbol="AAPL",
                quantity=100.0,
                avg_cost=100.0,
                entry_price=100.0,
                current_price=100.0,
                market_value=10_000.0,
            ),
            Position(
                symbol="MSFT",
                quantity=200.0,
                avg_cost=200.0,
                entry_price=200.0,
                current_price=200.0,
                market_value=40_000.0,
            ),
        ]
        portfolio = PaperPortfolio(store)
        actions = [RiskAction(action_type="daily_halt", symbol="", shares=0.0, reason="test")]
        result = portfolio.process_risk_actions(actions, _bar())
        assert len(result.violations) == 0
        aapl = next(p for p in store.saved_positions if p.symbol == "AAPL")
        msft = next(p for p in store.saved_positions if p.symbol == "MSFT")
        assert aapl.quantity == 0.0
        assert msft.quantity == 0.0

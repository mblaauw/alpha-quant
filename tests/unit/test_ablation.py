"""Unit tests for shadow ablation books (alpha_quant.domain.ablation)."""

import math
from datetime import date, datetime

from alpha_quant.adapters.fake.fixture_store import FixtureStore
from alpha_quant.domain.ablation import (
    NO_CROWDING_VETO_CONFIG,
    NO_INSIDER_CONFIG,
    RULES_ONLY_CONFIG,
    AblationComparison,
    AblationConfig,
    ShadowBook,
    compute_ablation_comparison,
    compute_spy_buy_and_hold,
)
from alpha_quant.domain.models import Bar, Order, Position, Quote
from alpha_quant.domain.risk import RiskAction


def _make_bar(symbol: str, date: date, open: float, high: float, low: float, close: float) -> Bar:
    return Bar(
        symbol=symbol, date=date, open=open, high=high, low=low, close=close, volume=1_000_000
    )


def _make_order(symbol: str, qty: float, price: float) -> Order:
    return Order(
        order_id=f"order_{symbol}",
        symbol=symbol,
        action="buy",
        quantity=qty,
        order_type="market",
        status="new",
    )


def _make_quote(symbol: str, price: float) -> Quote:
    return Quote(
        symbol=symbol,
        timestamp=datetime.now(),
        bid=price * 0.999,
        ask=price * 1.001,
    )


class TestAblationConfig:
    def test_paper_defaults(self) -> None:
        c = AblationConfig()
        assert c.disable_insider is False
        assert c.disable_crowding_veto is False

    def test_no_insider(self) -> None:
        assert NO_INSIDER_CONFIG.disable_insider is True
        assert NO_INSIDER_CONFIG.disable_crowding_veto is False

    def test_no_crowding_veto(self) -> None:
        assert NO_CROWDING_VETO_CONFIG.disable_insider is False
        assert NO_CROWDING_VETO_CONFIG.disable_crowding_veto is True

    def test_disable_both(self) -> None:
        c = AblationConfig(disable_insider=True, disable_crowding_veto=True)
        assert c.disable_insider is True
        assert c.disable_crowding_veto is True

    def test_rules_only(self) -> None:
        assert RULES_ONLY_CONFIG.disable_insider is True
        assert RULES_ONLY_CONFIG.disable_crowding_veto is True

    def test_shadow_configs_include_rules_only(self) -> None:
        from alpha_quant.domain.ablation import SHADOW_CONFIGS

        assert "RULES_ONLY" in SHADOW_CONFIGS
        assert SHADOW_CONFIGS["RULES_ONLY"].disable_insider is True
        assert SHADOW_CONFIGS["RULES_ONLY"].disable_crowding_veto is True


class TestComputeAblationComparison:
    def test_returns_none_with_fewer_than_10_returns(self) -> None:
        result = compute_ablation_comparison(
            [0.01] * 5,
            [0.02] * 5,
            mechanism="NO_INSIDER",
        )
        assert result is None

    def test_returns_comparison_with_sufficient_data(self) -> None:
        paper_returns = [0.001] * 100
        ablation_returns = [0.002] * 100
        result = compute_ablation_comparison(
            paper_returns,
            ablation_returns,
            mechanism="NO_INSIDER",
        )
        assert result is not None
        assert result.mechanism == "NO_INSIDER"

    def test_higher_sharpe_is_flagged(self) -> None:
        paper_returns = [0.001, 0.002, -0.001, 0.003, -0.002] * 20
        better_returns = [0.003, 0.004, 0.001, 0.005, -0.001] * 20
        result = compute_ablation_comparison(
            paper_returns,
            better_returns,
            mechanism="NO_CROWDING_VETO",
        )
        assert result is not None
        assert result.flagged is True
        assert result.diff > 0

    def test_lower_sharpe_not_flagged(self) -> None:
        paper_returns = [0.003, 0.004, 0.001, 0.005, -0.001] * 20
        worse_returns = [0.001, 0.002, -0.001, 0.003, -0.002] * 20
        result = compute_ablation_comparison(
            paper_returns,
            worse_returns,
            mechanism="NO_INSIDER",
        )
        assert result is not None
        assert result.flagged is False
        assert result.diff < 0

    def test_equal_sharpe_not_flagged(self) -> None:
        returns = [0.001] * 100
        result = compute_ablation_comparison(
            returns,
            returns,
            mechanism="NO_INSIDER",
        )
        assert result is not None
        assert result.flagged is False
        assert result.diff == 0.0

    def test_sharpe_zero_when_no_volatility(self) -> None:
        flat = [1.0] * 100
        result = compute_ablation_comparison(flat, flat, mechanism="NO_INSIDER")
        assert result is not None
        assert math.isfinite(result.ablation_sharpe)
        assert math.isfinite(result.paper_sharpe)

    def test_comparison_rounds_to_4_decimals(self) -> None:
        paper = [0.00123456] * 100
        ablation = [0.00234567] * 100
        result = compute_ablation_comparison(
            paper,
            ablation,
            mechanism="NO_INSIDER",
        )
        assert result is not None
        assert len(str(result.paper_sharpe).split(".")[1]) <= 4
        assert len(str(result.ablation_sharpe).split(".")[1]) <= 4


class TestAblationComparison:
    def test_attributes(self) -> None:
        c = AblationComparison(
            mechanism="NO_INSIDER",
            ablation_sharpe=0.5,
            paper_sharpe=0.3,
            diff=0.2,
            flagged=True,
        )
        assert c.mechanism == "NO_INSIDER"
        assert c.ablation_sharpe == 0.5
        assert c.paper_sharpe == 0.3
        assert c.diff == 0.2
        assert c.flagged is True


class TestShadowBookInitialize:
    def test_sets_cash_and_saves_snapshot(self) -> None:
        store = FixtureStore()
        book = ShadowBook(store, "TEST_BOOK", AblationConfig())
        book.initialize(100_000.0, date(2025, 1, 2))
        assert book.cash == 100_000.0
        snap = store.load_latest_portfolio_snapshot("TEST_BOOK")
        assert snap is not None
        assert snap.cash == 100_000.0
        assert snap.equity == 100_000.0
        assert snap.book == "TEST_BOOK"

    def test_recovers_cash_on_init(self) -> None:
        store = FixtureStore()
        book = ShadowBook(store, "RECOVER", AblationConfig())
        book.initialize(50_000.0, date(2025, 1, 2))
        book2 = ShadowBook(store, "RECOVER", AblationConfig())
        assert book2.cash == 50_000.0

    def test_initial_positions_empty(self) -> None:
        store = FixtureStore()
        book = ShadowBook(store, "EMPTY", AblationConfig())
        book.initialize(100_000.0, date(2025, 1, 2))
        assert book.positions == []


class TestShadowBookEntryOrders:
    def test_fills_buy_order(self) -> None:
        store = FixtureStore()
        book = ShadowBook(store, "ENTRY", AblationConfig())
        book.initialize(100_000.0, date(2025, 1, 2))

        bar = _make_bar("AAPL", date(2025, 1, 3), 150.0, 152.0, 149.0, 151.0)
        order = _make_order("AAPL", 100, 150.0)
        result = book.process_entry_orders([order], bar, 149.95)

        assert len(result.fills) == 1
        assert result.fills[0].symbol == "AAPL"
        assert result.fills[0].quantity == 100
        fill_cost = round(100 * result.fills[0].price, 2)
        assert book.cash == round(100_000.0 - fill_cost, 2)

    def test_insufficient_cash_violation(self) -> None:
        store = FixtureStore()
        book = ShadowBook(store, "CASH", AblationConfig())
        book.initialize(100.0, date(2025, 1, 2))

        bar = _make_bar("AAPL", date(2025, 1, 3), 200.0, 205.0, 199.0, 202.0)
        order = _make_order("AAPL", 100, 200.0)
        result = book.process_entry_orders([order], bar, 199.99)

        assert len(result.fills) == 0
        assert len(result.violations) == 1
        assert result.violations[0].check == "I7_insufficient_cash"
        assert book.cash == 100.0

    def test_fill_gap_blocks_entry(self) -> None:
        store = FixtureStore()
        book = ShadowBook(store, "GAP", AblationConfig())
        book.initialize(100_000.0, date(2025, 1, 2))

        bar = _make_bar("AAPL", date(2025, 1, 3), 200.0, 205.0, 199.0, 202.0)
        order = _make_order("AAPL", 100, 150.0)
        result = book.process_entry_orders([order], bar, 150.0)

        assert len(result.fills) == 0
        assert book.cash == 100_000.0

    def test_adds_to_existing_position(self) -> None:
        store = FixtureStore()
        book = ShadowBook(store, "ADD", AblationConfig())
        book.initialize(100_000.0, date(2025, 1, 2))
        bar = _make_bar("AAPL", date(2025, 1, 3), 150.0, 152.0, 149.0, 151.0)

        book.process_entry_orders([_make_order("AAPL", 100, 150.0)], bar, 149.99)
        book.process_entry_orders([_make_order("AAPL", 50, 151.0)], bar, 150.0)

        assert len(book.positions) == 1
        assert book.positions[0].quantity == 150


class TestShadowBookRiskActions:
    def test_stop_exit_sells_position(self) -> None:
        store = FixtureStore()
        book = ShadowBook(store, "STOP", AblationConfig())
        book.initialize(100_000.0, date(2025, 1, 2))

        bar = _make_bar("AAPL", date(2025, 1, 3), 150.0, 152.0, 140.0, 145.0)
        order = _make_order("AAPL", 100, 150.0)
        book.process_entry_orders([order], bar, 149.99)

        pos = book.positions[0]
        updated_pos = pos.model_copy(update={"stop_price": 145.0})
        book._positions["AAPL"] = updated_pos

        actions = [RiskAction(action_type="stop", symbol="AAPL", shares=100, reason="stop test")]
        result = book.process_risk_actions(actions, bar)

        assert len(result.fills) == 1
        assert result.fills[0].quantity < 0
        assert len([p for p in book.positions if p.quantity > 0]) == 0

    def test_partial_take_reduces_position(self) -> None:
        store = FixtureStore()
        book = ShadowBook(store, "PARTIAL", AblationConfig())
        book.initialize(100_000.0, date(2025, 1, 2))

        bar = _make_bar("AAPL", date(2025, 1, 3), 150.0, 152.0, 149.0, 151.0)
        order = _make_order("AAPL", 100, 150.0)
        book.process_entry_orders([order], bar, 149.99)

        actions = [
            RiskAction(action_type="partial_take", symbol="AAPL", shares=50, reason="take profit")
        ]
        result = book.process_risk_actions(actions, bar)

        assert len(result.fills) == 1
        remaining = [p for p in book.positions if p.quantity > 0]
        assert len(remaining) == 1
        assert remaining[0].quantity == 50

    def test_unknown_position_skipped(self) -> None:
        store = FixtureStore()
        book = ShadowBook(store, "SKIP", AblationConfig())
        book.initialize(100_000.0, date(2025, 1, 2))

        bar = _make_bar("AAPL", date(2025, 1, 3), 150.0, 152.0, 149.0, 151.0)
        actions = [RiskAction(action_type="stop", symbol="MISSING", shares=100, reason="no pos")]
        result = book.process_risk_actions(actions, bar)

        assert len(result.fills) == 0


class TestShadowBookMarkToMarket:
    def test_marks_positions_and_returns_snapshot(self) -> None:
        store = FixtureStore()
        book = ShadowBook(store, "MARK", AblationConfig())
        book.initialize(100_000.0, date(2025, 1, 2))

        bar = _make_bar("AAPL", date(2025, 1, 3), 150.0, 152.0, 149.0, 151.0)
        book.process_entry_orders([_make_order("AAPL", 100, 150.0)], bar, 149.99)
        fill_price = book.positions[0].avg_cost
        fill_cost = round(100 * fill_price, 2)

        snap = book.mark_to_market(date(2025, 1, 3), {"AAPL": 155.0}, prev_equity=100_000.0)

        assert snap.date == date(2025, 1, 3)
        assert snap.book == "MARK"
        expected_mark = round(100 * 155.0, 2)
        expected_equity = round((100_000.0 - fill_cost) + expected_mark, 2)
        assert snap.equity == expected_equity

    def test_tracks_daily_returns(self) -> None:
        store = FixtureStore()
        book = ShadowBook(store, "RETURNS", AblationConfig())
        book.initialize(100_000.0, date(2025, 1, 2))

        bar = _make_bar("AAPL", date(2025, 1, 3), 150.0, 152.0, 149.0, 151.0)
        book.process_entry_orders([_make_order("AAPL", 100, 150.0)], bar, 149.99)
        book.mark_to_market(date(2025, 1, 3), {"AAPL": 151.0}, prev_equity=100_000.0)

        assert len(book.daily_returns) > 0

    def test_cleans_up_zero_quantity_positions(self) -> None:
        store = FixtureStore()
        book = ShadowBook(store, "CLEAN", AblationConfig())
        book.initialize(100_000.0, date(2025, 1, 2))

        book._positions["DEAD"] = Position(symbol="DEAD", quantity=0, avg_cost=100.0)
        book.mark_to_market(date(2025, 1, 3), {"AAPL": 150.0})

        symbols = [p.symbol for p in book.positions]
        assert "DEAD" not in symbols


class TestShadowBookSelfConsistency:
    def test_returns_empty_when_consistent(self) -> None:
        store = FixtureStore()
        book = ShadowBook(store, "CONSIST", AblationConfig())
        book.initialize(100_000.0, date(2025, 1, 2))

        violations = book.self_consistency_check()
        assert len(violations) == 0

    def test_detects_mismatch(self) -> None:
        store = FixtureStore()
        book = ShadowBook(store, "MISMATCH", AblationConfig())
        book.initialize(100_000.0, date(2025, 1, 2))

        bar = _make_bar("AAPL", date(2025, 1, 3), 150.0, 152.0, 149.0, 151.0)
        book.process_entry_orders([_make_order("AAPL", 100, 150.0)], bar, 149.99)

        book._cash = 0.0
        violations = book.self_consistency_check()

        assert any("I6_gross_exposure" in v.check for v in violations)


class TestComputeSpyBuyAndHold:
    def test_returns_initial_equity_with_no_bars(self) -> None:
        curve = compute_spy_buy_and_hold([], date(2025, 1, 2), date(2025, 1, 3), 100_000.0)
        assert curve == [100_000.0]

    def test_computes_equity_curve(self) -> None:
        spy_bars = [
            _make_bar("SPY", date(2025, 1, 2), 400.0, 402.0, 399.0, 401.0),
            _make_bar("SPY", date(2025, 1, 3), 402.0, 405.0, 401.0, 404.0),
            _make_bar("SPY", date(2025, 1, 6), 404.0, 406.0, 403.0, 405.0),
        ]
        curve = compute_spy_buy_and_hold(spy_bars, date(2025, 1, 2), date(2025, 1, 6), 100_000.0)

        assert len(curve) == len(spy_bars)
        assert curve[0] == 100_000.0
        assert curve[1] > 100_000.0
        assert curve[2] > curve[1]


class TestPortfolioSnapshotBook:
    def test_default_book_is_paper(self) -> None:
        from alpha_quant.domain.models import PortfolioSnapshot

        snap = PortfolioSnapshot(date=date(2025, 1, 2), cash=100_000.0, equity=100_000.0)
        assert snap.book == "PAPER"

    def test_shadow_book_name(self) -> None:
        from alpha_quant.domain.models import PortfolioSnapshot

        snap = PortfolioSnapshot(
            date=date(2025, 1, 2), cash=100_000.0, equity=100_000.0, book="RULES_ONLY"
        )
        assert snap.book == "RULES_ONLY"

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast

from alpha_quant.application.query import risk as risk_query


class _Store:
    def current_halt(self, book_id: object) -> SimpleNamespace | None:
        return None

    def list_positions(self, book_id: object) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(
                symbol="NVDA",
                quantity=Decimal("25"),
                avg_cost=Decimal("1000"),
                current_price=Decimal("11200"),
                market_value=Decimal("280000"),
                unrealized_pl=Decimal("30000"),
                stop_price=Decimal("10650"),
            ),
            SimpleNamespace(
                symbol="JPM",
                quantity=Decimal("100"),
                avg_cost=Decimal("190"),
                current_price=Decimal("200"),
                market_value=Decimal("20000"),
                unrealized_pl=Decimal("1000"),
                stop_price=Decimal("180"),
            ),
        ]

    def load_portfolio(self, book_id: object) -> SimpleNamespace:
        return SimpleNamespace(cash=Decimal("50000"))


def test_risk_summary_returns_gui_contract_placeholder(monkeypatch: Any) -> None:
    def fake_with_uow(query_fn: Any, database_url: str | None = None) -> dict[str, object]:
        return query_fn(SimpleNamespace(store=_Store()))

    monkeypatch.setattr(risk_query, "with_uow", fake_with_uow)

    data = risk_query.RiskService().summary()

    for key in (
        "as_of",
        "equity",
        "posture",
        "headline",
        "var",
        "component_var",
        "scenarios",
        "concentration",
        "factors",
        "liquidity",
        "limits",
        "events",
    ):
        assert key in data

    assert data["equity"] == 350000.0
    posture = cast(dict[str, object], data["posture"])
    var = cast(dict[str, object], data["var"])
    method_params = cast(dict[str, object], var["method_params"])
    headline = cast(dict[str, object], data["headline"])
    component_var = cast(list[dict[str, object]], data["component_var"])
    concentration = cast(dict[str, object], data["concentration"])
    sectors = cast(list[dict[str, object]], concentration["sectors"])
    limits = cast(list[dict[str, object]], data["limits"])

    assert posture["state"] == "elevated"
    assert method_params["placeholder"] is True
    assert headline["var_1d_99_pct"] == 0.036
    assert len(component_var) == 2
    assert sectors[0]["name"] == "Technology"
    assert limits[0]["breach"] is True


class _ClearedHaltStore(_Store):
    def current_halt(self, book_id: object) -> SimpleNamespace:
        return SimpleNamespace(
            halted=False,
            reason=SimpleNamespace(value="manual"),
            details="Cleared halt should not render",
            halted_at=None,
        )


def test_risk_summary_suppresses_cleared_halt(monkeypatch: Any) -> None:
    def fake_with_uow(query_fn: Any, database_url: str | None = None) -> dict[str, object]:
        return query_fn(SimpleNamespace(store=_ClearedHaltStore()))

    monkeypatch.setattr(risk_query, "with_uow", fake_with_uow)

    data = risk_query.RiskService().summary()

    assert data["halted"] is False
    assert data["halt"] is None

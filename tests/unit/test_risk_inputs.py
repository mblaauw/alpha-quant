"""Tests for risk input pipeline (WS1)."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from alpha_quant.application.risk.inputs import load_inputs, RiskInputs


def _mock_session(rows: list[dict[str, str]] | None = None) -> Any:
    """Create a mock session that returns sector rows."""
    if rows is None:
        rows = []
    return SimpleNamespace(
        execute=lambda *a, **kw: SimpleNamespace(
            fetchall=lambda: [SimpleNamespace(_mapping={k: v for k, v in r.items()}) for r in rows]
        )
    )


class _Store:
    def __init__(self) -> None:
        self.session = _mock_session()

    def current_halt(self, book_id: object) -> SimpleNamespace | None:
        return None

    def list_positions(self, book_id: object) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(
                symbol="NVDA",
                quantity=Decimal("25"),
                market_value=Decimal("280000"),
                current_price=Decimal("11200"),
            ),
            SimpleNamespace(
                symbol="JPM",
                quantity=Decimal("100"),
                market_value=Decimal("20000"),
                current_price=Decimal("200"),
            ),
        ]

    def load_portfolio(self, book_id: object) -> SimpleNamespace:
        return SimpleNamespace(cash=Decimal("50000"))


class _StoreWithSectors(_Store):
    def __init__(self) -> None:
        self.session = _mock_session(
            [
                {"symbol": "NVDA", "sector": "Technology"},
                {"symbol": "JPM", "sector": "Financials"},
            ]
        )


class _StoreNoPositions:
    def __init__(self) -> None:
        self.session = _mock_session()

    def current_halt(self, book_id: object) -> SimpleNamespace | None:
        return None

    def list_positions(self, book_id: object) -> list[SimpleNamespace]:
        return []

    def load_portfolio(self, book_id: object) -> SimpleNamespace:
        return SimpleNamespace(cash=Decimal("0"))


def _fake_with_uow(store: Any) -> Any:
    def wrapper(query_fn: Any, database_url: str | None = None) -> Any:
        return query_fn(SimpleNamespace(store=store))

    return wrapper


def _patch_with_uow(monkeypatch: Any, store: Any) -> None:
    """Monkeypatch the shared module's with_uow (where inputs.py imports it)."""
    from alpha_quant.application.query import shared

    monkeypatch.setattr(shared, "with_uow", _fake_with_uow(store))


def test_load_inputs_returns_correct_equity(monkeypatch: Any) -> None:
    _patch_with_uow(monkeypatch, _Store())

    result = load_inputs()

    assert isinstance(result, RiskInputs)
    assert result.equity == 350000.0  # 280000 + 20000 + 50000
    assert result.cash == 50000.0
    assert len(result.positions) == 2
    assert abs(sum(result.weights) - 0.857) < 0.01  # NVDA 0.8 + JPM 0.057


def test_load_inputs_sectors_from_security_reference(monkeypatch: Any) -> None:
    _patch_with_uow(monkeypatch, _StoreWithSectors())

    result = load_inputs()

    assert result.positions[0].sector == "Technology"
    assert result.positions[1].sector == "Financials"
    assert result.sectors == ["Technology", "Financials"]


def test_load_inputs_no_positions_defaults_equity(monkeypatch: Any) -> None:
    _patch_with_uow(monkeypatch, _StoreNoPositions())

    result = load_inputs()

    assert result.equity == 0.0
    assert result.positions == []
    assert result.weights == []


def test_load_inputs_no_active_halt(monkeypatch: Any) -> None:
    _patch_with_uow(monkeypatch, _Store())

    result = load_inputs()

    assert result.halt_active is False
    assert result.halt_details is None

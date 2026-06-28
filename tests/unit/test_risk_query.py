"""Tests for the risk query service contract."""

from __future__ import annotations

from typing import Any

from alpha_quant.application.risk import RiskEngine


def test_risk_summary_returns_gui_contract() -> None:
    data = RiskEngine().run()

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
        assert key in data, f"Missing key: {key}"

    assert data["halted"] is not None
    assert data["posture"]["state"] in ("ready", "elevated", "halt")


def test_risk_summary_empty_book_has_no_placeholder_flag() -> None:
    data = RiskEngine().run()
    var_section = data.get("var", {})
    method_params = var_section.get("method_params", {})
    assert "placeholder" not in method_params

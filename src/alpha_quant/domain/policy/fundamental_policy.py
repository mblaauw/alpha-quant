from __future__ import annotations

from alpha_quant.domain.decision_context import DecisionContext


def evaluate(context: DecisionContext) -> bool:
    """Fundamental quality gate. Returns True if the symbol passes.

    Policy applies thresholds to Alpha-Lake fundamental metrics.
    No ratios are calculated locally.
    """
    pe = context.fundamental_value("fundamentals.valuation.pe_ttm")
    debt_to_equity = context.fundamental_value("fundamentals.financial_health.debt_to_equity_ttm")
    current_ratio = context.fundamental_value("fundamentals.financial_health.current_ratio_ttm")
    gross_margin = context.fundamental_value("fundamentals.profitability.gross_margin_ttm")
    earnings_yield = context.fundamental_value("fundamentals.valuation.earnings_yield_ttm")

    if pe is not None and pe > 0 and pe > 100:
        return False

    if debt_to_equity is not None and debt_to_equity > 5.0:
        return False

    if current_ratio is not None and current_ratio < 0.5:
        return False

    if gross_margin is not None and gross_margin < -0.5:
        return False

    if earnings_yield is not None and earnings_yield < -0.20:
        return False

    return True

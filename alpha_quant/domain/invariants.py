from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from alpha_quant.domain.models import Position


class InvariantViolation(BaseModel):
    model_config = ConfigDict(frozen=True)
    check: str
    detail: str


def check_invariants(
    equity: float,
    cash: float,
    positions: list[Position],
    max_gross_exposure: float = 0.80,
    risk_tolerance_pct: float = 0.02,
) -> list[InvariantViolation]:
    violations: list[InvariantViolation] = []

    violations.extend(_check_equity_consistency(equity, cash, positions))
    violations.extend(_check_gross_exposure(equity, positions, max_gross_exposure))
    violations.extend(_check_position_risk(equity, positions, risk_tolerance_pct))

    return violations


def _check_equity_consistency(
    equity: float,
    cash: float,
    positions: list[Position],
) -> list[InvariantViolation]:
    mark = sum(p.market_value or 0 for p in positions)
    diff = abs(cash + mark - equity)
    if diff >= 0.01:
        return [
            InvariantViolation(
                check="I1_cash_plus_mark_equals_equity",
                detail=(
                    f"cash={cash:.2f} + mark={mark:.2f} = {cash + mark:.2f}"
                    f" != equity={equity:.2f} (diff={diff:.4f})"
                ),
            )
        ]
    return []


def _check_gross_exposure(
    equity: float,
    positions: list[Position],
    max_gross_exposure: float,
) -> list[InvariantViolation]:
    if equity <= 0:
        return []
    gross = sum(abs(p.market_value or 0) for p in positions)
    exposure_pct = gross / equity
    if exposure_pct > max_gross_exposure:
        return [
            InvariantViolation(
                check="I6_gross_exposure",
                detail=(
                    f"gross={gross:.2f} ({exposure_pct * 100:.1f}%)"
                    f" > max={max_gross_exposure * 100:.0f}% of equity={equity:.2f}"
                ),
            )
        ]
    return []


def _check_position_risk(
    equity: float,
    positions: list[Position],
    risk_tolerance_pct: float,
) -> list[InvariantViolation]:
    if equity <= 0:
        return []
    violations: list[InvariantViolation] = []
    for p in positions:
        risk = _position_risk(p)
        if risk is None:
            continue
        risk_pct = risk / equity
        if risk_pct > risk_tolerance_pct:
            violations.append(
                InvariantViolation(
                    check="I5_risk_at_stop",
                    detail=(
                        f"{p.symbol}: risk={risk:.2f} ({risk_pct * 100:.2f}%)"
                        f" > {risk_tolerance_pct * 100:.0f}% of equity"
                    ),
                )
            )
    return violations


def _position_risk(position: Position) -> float | None:
    if position.stop_price is None or position.avg_cost is None:
        return None
    risk_per_share = position.avg_cost - position.stop_price
    if risk_per_share <= 0:
        return None
    return risk_per_share * position.quantity

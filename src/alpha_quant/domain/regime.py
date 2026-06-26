from __future__ import annotations

from typing import Literal

Regime = Literal["RISK_ON", "CAUTION", "RISK_OFF"]

REGIME_MULTIPLIERS: dict[Regime, float] = {
    "RISK_ON": 1.0,
    "CAUTION": 0.5,
    "RISK_OFF": 0.0,
}

RISK_ON: Regime = "RISK_ON"
CAUTION: Regime = "CAUTION"
RISK_OFF: Regime = "RISK_OFF"

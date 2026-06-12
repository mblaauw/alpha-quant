from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

AblationMechanism = Literal["NO_INSIDER", "NO_CROWDING_VETO"]
ABLATION_MECHANISMS: list[AblationMechanism] = ["NO_INSIDER", "NO_CROWDING_VETO"]


@dataclass
class AblationConfig:
    disable_insider: bool = False
    disable_crowding_veto: bool = False


PAPER_CONFIG = AblationConfig()
NO_INSIDER_CONFIG = AblationConfig(disable_insider=True)
NO_CROWDING_VETO_CONFIG = AblationConfig(disable_crowding_veto=True)

SHADOW_CONFIGS: dict[str, AblationConfig] = {
    "NO_INSIDER": NO_INSIDER_CONFIG,
    "NO_CROWDING_VETO": NO_CROWDING_VETO_CONFIG,
}


@dataclass
class AblationComparison:
    mechanism: str
    ablation_sharpe: float
    paper_sharpe: float
    diff: float
    flagged: bool


def compute_ablation_comparison(
    paper_returns: list[float],
    ablation_returns: list[float],
    mechanism: str,
) -> AblationComparison | None:
    if len(paper_returns) < 10 or len(ablation_returns) < 10:
        return None

    paper_sharpe = _annualized_sharpe(paper_returns)
    ablation_sharpe = _annualized_sharpe(ablation_returns)

    flagged = ablation_sharpe > paper_sharpe

    return AblationComparison(
        mechanism=mechanism,
        ablation_sharpe=round(ablation_sharpe, 4),
        paper_sharpe=round(paper_sharpe, 4),
        diff=round(ablation_sharpe - paper_sharpe, 4),
        flagged=flagged,
    )


def _annualized_sharpe(returns: list[float]) -> float:
    arr = np.array(returns)
    if np.std(arr) < 1e-10:
        return 0.0
    return float(np.mean(arr) / np.std(arr) * np.sqrt(252.0))

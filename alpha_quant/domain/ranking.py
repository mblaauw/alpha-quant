from __future__ import annotations

from alpha_quant.domain.models import Candidate


def rank(
    candidates: list[Candidate],
    max_positions: int,
    current_count: int,
    symbol_adv: dict[str, float] | None = None,
) -> list[Candidate]:
    slots = max_positions - current_count
    if slots <= 0:
        return []

    passed = [c for c in candidates if _passes_gates(c)]
    if not passed:
        return []

    scored = [
        Candidate(
            symbol=c.symbol,
            date=c.date,
            scores=c.scores,
            composite_score=_compute_composite(c.scores),
            regime=c.regime,
            gate_results=c.gate_results,
        )
        for c in passed
    ]

    above_threshold = [c for c in scored if c.composite_score > 0.5]
    above_threshold.sort(
        key=lambda c: (-c.composite_score, -_adv(c.symbol, symbol_adv)),
    )

    return above_threshold[:slots]


def _passes_gates(candidate: Candidate) -> bool:
    if candidate.block_reason is not None:
        return False
    return all(candidate.gate_results.values())


def _compute_composite(scores: dict[str, float]) -> float:
    technical = scores.get("technical", 0.0)
    momentum = scores.get("momentum", 0.0)
    insider = scores.get("insider")

    if insider is not None:
        composite = 0.6 * technical + 0.25 * momentum + 0.15 * insider
    else:
        composite = 0.70 * technical + 0.30 * momentum

    return round(max(0.0, min(1.0, composite)), 4)


def _adv(symbol: str, symbol_adv: dict[str, float] | None) -> float:
    if symbol_adv is None:
        return 0.0
    return symbol_adv.get(symbol, 0.0)

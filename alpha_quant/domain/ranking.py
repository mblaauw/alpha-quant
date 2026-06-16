"""Candidate ranking and sector-diversified selection."""

from __future__ import annotations

from alpha_quant.domain.models import Candidate
from alpha_quant.domain.scoring import compute_composite


def rank(
    candidates: list[Candidate],
    max_positions: int,
    current_count: int,
    symbol_adv: dict[str, float] | None = None,
    max_sector_pct: float = 0.25,
    sector_map: dict[str, str] | None = None,
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
            composite_score=compute_composite(c.scores),
            regime=c.regime,
            gate_results=c.gate_results,
            sector=c.sector,
        )
        for c in passed
    ]

    above_threshold = [c for c in scored if c.composite_score > 0.5]
    above_threshold.sort(
        key=lambda c: (-c.composite_score, -_adv(c.symbol, symbol_adv)),
    )

    selected: list[Candidate] = []
    sector_counts: dict[str, int] = {}
    max_per_sector = max(1, int(slots * max_sector_pct))

    for cand in above_threshold:
        if len(selected) >= slots:
            break
        sec = sector_map.get(cand.symbol, cand.sector) if sector_map else cand.sector
        if sec and sector_counts.get(sec, 0) >= max_per_sector:
            continue
        selected.append(cand)
        if sec:
            sector_counts[sec] = sector_counts.get(sec, 0) + 1

    return selected


def _passes_gates(candidate: Candidate) -> bool:
    if candidate.block_reason is not None:
        return False
    return all(candidate.gate_results.values())


def _adv(symbol: str, symbol_adv: dict[str, float] | None) -> float:
    if symbol_adv is None:
        return 0.0
    return symbol_adv.get(symbol, 0.0)

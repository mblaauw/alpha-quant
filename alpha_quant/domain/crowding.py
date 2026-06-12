from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class CrowdingVerdict:
    blocked: bool
    blocked_until: date | None = None
    reason: str | None = None


def evaluate(
    z_score: float | None,
    blocked_until: date | None,
    as_of_date: date,
) -> CrowdingVerdict:
    if blocked_until is not None and as_of_date < blocked_until:
        return CrowdingVerdict(
            blocked=True,
            blocked_until=blocked_until,
            reason=f"crowding block active until {blocked_until}",
        )

    if z_score is None or z_score <= 3:
        return CrowdingVerdict(blocked=False)

    block_end = as_of_date + timedelta(days=14)
    return CrowdingVerdict(
        blocked=True,
        blocked_until=block_end,
        reason=f"z-score {z_score:.2f} > 3, blocked until {block_end}",
    )

from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel, ConfigDict


class CrowdingVerdict(BaseModel):
    model_config = ConfigDict(frozen=True)
    blocked: bool
    blocked_until: date | None = None
    reason: str | None = None


_BLOCK_DAYS = 14


def evaluate(
    z_score: float | None,
    blocked_until: date | None,
    as_of_date: date,
    block_days: int = _BLOCK_DAYS,
) -> CrowdingVerdict:
    if blocked_until is not None and as_of_date < blocked_until:
        if z_score is not None and z_score > 3:
            extended = max(blocked_until, as_of_date + timedelta(days=block_days))
            return CrowdingVerdict(
                blocked=True,
                blocked_until=extended,
                reason=f"z-score {z_score:.2f} extended block until {extended}",
            )
        return CrowdingVerdict(
            blocked=True,
            blocked_until=blocked_until,
            reason=f"crowding block active until {blocked_until}",
        )

    if z_score is None or z_score <= 3:
        return CrowdingVerdict(blocked=False)

    block_end = as_of_date + timedelta(days=block_days)
    return CrowdingVerdict(
        blocked=True,
        blocked_until=block_end,
        reason=f"z-score {z_score:.2f} > 3, blocked until {block_end}",
    )

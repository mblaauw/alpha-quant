from __future__ import annotations

from datetime import date, datetime, timedelta

from alpha_quant.domain.decision_context import DecisionContext

_BLACKOUT_DAYS = 14


def evaluate(context: DecisionContext, as_of: date | None = None) -> bool:
    """Earnings blackout gate.

    Returns True if the symbol is NOT in blackout (trading allowed).
    Returns False if the symbol is within the blackout window of a
    confirmed earnings event from Alpha-Lake.
    """
    today = as_of or context.as_of.date()
    window_end = today + timedelta(days=_BLACKOUT_DAYS)

    for event in context.earnings_events:
        event_date = _parse_date(event.effective_date)
        if event_date is None:
            continue
        if today <= event_date <= window_end:
            return False
    return True


class BlackoutSchedule:
    def __init__(self) -> None:
        self._cache: dict[str, date] = {}

    def is_blocked(self, symbol: str, context: DecisionContext, as_of: date | None = None) -> bool:
        today = as_of or context.as_of.date()
        blocked_until = self._cache.get(symbol)
        if blocked_until and today < blocked_until:
            return True

        if not evaluate(context, as_of=today):
            blocked_until = today + timedelta(days=_BLACKOUT_DAYS)
            self._cache[symbol] = blocked_until
            return True

        return False

    def clear(self, symbol: str) -> None:
        self._cache.pop(symbol, None)


def _parse_date(raw: str) -> date | None:
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except (ValueError, TypeError):  # fmt: skip
        return None

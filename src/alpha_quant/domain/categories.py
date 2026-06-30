"""M1-M8 category mapping — authoritative, single source of truth.

Used by both decision API serialization (decisions.py) and console routes.
"""

from __future__ import annotations

from typing import Any

# Maps component name or category to (M-id, type, question)
# Includes both Title Case display names and lowercase engine category strings
M_CATEGORY: dict[str, tuple[str, str, str]] = {
    # M1 — Universe & investability
    "Universe": ("M1", "hard", "Can this security be traded?"),
    "Universe & Investability": ("M1", "hard", "Can this security be traded?"),
    # M2 — Market regime & posture
    "Regime": ("M2", "soft", "Should long risk be deployed?"),
    "Market Regime": ("M2", "soft", "Should long risk be deployed?"),
    # M3 — Technical state & leadership
    "Technical": ("M3", "score", "Is it a leader with a valid setup now?"),
    "Technical Trend": ("M3", "score", "Is it a leader with a valid setup now?"),
    "Momentum": ("M3", "score", "Is it a leader with a valid setup now?"),
    "technical": ("M3", "score", "Is it a leader with a valid setup now?"),
    "risk": ("M3", "score", "Is it a leader with a valid setup now?"),
    # M4 — Fundamental resilience
    "Fundamental": ("M4", "soft", "Is there a fundamental reason to avoid it?"),
    "Fundamental Resilience": ("M4", "soft", "Is there a fundamental reason to avoid it?"),
    "fundamental": ("M4", "soft", "Is there a fundamental reason to avoid it?"),
    # M5 — Insider behaviour
    "Insider": ("M5", "evidence", "Is insider activity supportive?"),
    "Insider Behaviour": ("M5", "evidence", "Is insider activity supportive?"),
    "insider": ("M5", "evidence", "Is insider activity supportive?"),
    # M6 — Crowding & attention
    "Attention": ("M6", "soft", "Is attention making the entry unsafe?"),
    "Crowding": ("M6", "soft", "Is attention making the entry unsafe?"),
    "sentiment": ("M6", "soft", "Is attention making the entry unsafe?"),
    # M7 — Known event & gap risk
    "Event Risk": ("M7", "hard", "Is event risk too large for normal risk controls?"),
    "Known Event": ("M7", "hard", "Is event risk too large for normal risk controls?"),
    "event": ("M7", "hard", "Is event risk too large for normal risk controls?"),
    # M8 — Rank & selection
    "Rank": ("M8", "score", "Is this the best remaining use of risk budget?"),
    "Ranking": ("M8", "score", "Is this the best remaining use of risk budget?"),
    # Portfolio and data quality mapped to M1 (universe/investability gate) and M8 (selection)
    "portfolio": ("M8", "score", "How does this fit in the portfolio?"),
    "data": ("M1", "hard", "Is the data fresh enough to trade?"),
}

M_NAMES: dict[str, str] = {
    "M1": "Universe & investability",
    "M2": "Market regime & posture",
    "M3": "Technical state & leadership",
    "M4": "Fundamental resilience",
    "M5": "Insider behaviour",
    "M6": "Crowding & attention",
    "M7": "Known event & gap risk",
    "M8": "Rank & selection",
}

M_QUESTIONS: dict[str, str] = {
    "M1": "Can this security be traded?",
    "M2": "Should long risk be deployed?",
    "M3": "Is it a leader with a valid setup now?",
    "M4": "Is there a fundamental reason to avoid it?",
    "M5": "Is insider activity supportive?",
    "M6": "Is attention making the entry unsafe?",
    "M7": "Is event risk too large for normal risk controls?",
    "M8": "Is this the best remaining use of risk budget?",
}


def resolve_mid(category: str) -> tuple[str, str, str]:
    """Resolve a category string to (M-id, type, question).

    Handles both engine-style ('technical') and display-style ('Technical') keys.
    Returns ('', 'score', '') for unmapped categories.
    """
    return M_CATEGORY.get(category, ("", "score", ""))


def module_from_component(component: Any) -> dict[str, Any]:
    """Map a ScorecardComponent to an M1-M8 module dict."""
    mid, mtype, question = resolve_mid(component.category)
    if not mid:
        return {
            "id": "",
            "name": component.name,
            "type": "score",
            "question": "",
            "state": component.state.value,
            "score": component.score if component.score else None,
            "archetype": None,
            "metrics": _parse_metrics(component.details_json),
            "reason": component.reason,
        }
    has_score = mtype in ("score", "evidence")
    return {
        "id": mid,
        "name": M_NAMES.get(mid, component.name),
        "type": mtype,
        "question": question,
        "state": _state_for_score(component.score, component.state.value, mtype),
        "score": round(component.score, 2) if has_score and component.score else None,
        "archetype": _parse_archetype(component.details_json) if mid == "M3" else None,
        "metrics": _parse_metrics(component.details_json),
        "reason": component.reason,
    }


def _state_for_score(score: float, state: str, mtype: str) -> str:
    if mtype == "hard":
        return "PASS" if state == "pass" else "FAIL"
    if mtype == "score" and score > 0:
        return f"RANK {score:.0f}" if score > 90 else f"SCORE {score:.0f}"
    return state.upper() if state else "PASS"


def _parse_metrics(details_json: str) -> list[dict[str, str]]:
    import json

    try:
        details = json.loads(details_json)
        raw = details.get("metrics", [])
        if isinstance(raw, list):
            return [
                {"k": str(m.get("k", "")), "v": str(m.get("v", ""))}
                for m in raw
                if isinstance(m, dict)
            ]
        return []
    except (json.JSONDecodeError, TypeError):  # fmt: skip
        return []


def _parse_archetype(details_json: str) -> str | None:
    import json

    try:
        details = json.loads(details_json)
        return details.get("archetype")
    except (json.JSONDecodeError, TypeError):  # fmt: skip
        return None

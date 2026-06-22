"""Ask/query interface for LLM-based analysis."""

from __future__ import annotations

import re

from domain.events import CandidateBlocked

_STOP_WORDS = {
    "A",
    "AN",
    "AND",
    "ARE",
    "AT",
    "CAN",
    "DID",
    "DO",
    "DOES",
    "FOR",
    "HAS",
    "HAD",
    "HOW",
    "IN",
    "IS",
    "ITS",
    "NOT",
    "OF",
    "ON",
    "OR",
    "THE",
    "TO",
    "WAS",
    "WERE",
    "WHAT",
    "WHY",
    "WHO",
    "WITH",
    "YOU",
    "YOUR",
    "ME",
    "MY",
    "WE",
    "OUR",
    "ALL",
    "ANY",
    "BUT",
    "DAY",
    "NOW",
    "OUT",
    "UP",
    "DOWN",
    "OFF",
    "TOP",
    "GET",
    "GOT",
    "LET",
    "PUT",
    "SET",
    "USE",
    "USED",
    "WAY",
    "MANY",
    "MORE",
    "MOST",
    "SOME",
    "THAN",
    "THAT",
    "THIS",
    "JUST",
    "ALSO",
    "INTO",
    "OVER",
    "THEN",
    "WHEN",
    "WHERE",
    "HERE",
    "THERE",
    "TODAY",
    "GOING",
    "BEING",
    "DOING",
    "HAVING",
    "MAKES",
    "TAKES",
    "GIVES",
    "LOOKS",
    "STILL",
    "NEVER",
    "ALWAYS",
    "TOTAL",
    "LEVEL",
}


def extract_symbol(query: str) -> str | None:
    words = re.findall(r"\b[A-Z]{1,5}\b", query)
    for w in words:
        if w not in _STOP_WORDS:
            return w
    return None


def is_concept_query(query: str) -> bool:
    lowered = query.lower()
    keywords = ["what is", "explain", "what does", "how does", "tell me about"]
    return any(kw in lowered for kw in keywords)


def format_blocked_answer(
    symbol: str,
    events: list[CandidateBlocked],
    days: int = 30,
) -> str:
    if not events:
        return f"No record of evaluating {symbol} in the last {days} days."

    lines = [f"**{symbol}** was blocked {len(events)} time(s) in the last {days} days:\n"]
    for e in events:
        lines.append(f"- {e.timestamp.date()}: gate={e.gate}, reason={e.reason}")
    return "\n".join(lines)


def ask(
    query: str,
    events: list[CandidateBlocked],
    concept_card: str | None = None,
    days: int = 30,
) -> str:
    if concept_card is not None:
        return concept_card

    symbol = extract_symbol(query)
    if symbol is None:
        return "I couldn't identify a symbol or concept in your query."

    blocked = [e for e in events if e.symbol.upper() == symbol]

    return format_blocked_answer(symbol, blocked, days)

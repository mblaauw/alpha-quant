from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from alpha_quant.domain.events import CandidateBlocked
from alpha_quant.ports.store import Store

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


def load_concept_card(concept_name: str, concepts_dir: Path) -> str | None:
    manifest_path = concepts_dir / "concepts.json"
    if not manifest_path.exists():
        return None
    import json

    with manifest_path.open() as f:
        cards = json.load(f)

    for card in cards:
        if concept_name.lower() in card["id"] or concept_name.lower() in card["title"].lower():
            card_path = concepts_dir / f"{card['id']}.md"
            if card_path.exists():
                return card_path.read_text()

    return None


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
    store: Store,
    concepts_dir: Path | None = None,
    days: int = 30,
    ref_date: date | None = None,
) -> str:
    if is_concept_query(query) and concepts_dir and concepts_dir.exists():
        for word in query.lower().split():
            card = load_concept_card(word, concepts_dir)
            if card is not None:
                return card

    symbol = extract_symbol(query)
    if symbol is None:
        return "I couldn't identify a symbol or concept in your query."

    cutoff_dt = datetime.combine(
        (ref_date or date.today()) - timedelta(days=days),
        datetime.min.time(),
        tzinfo=UTC,
    )
    all_events = store.load_events(since=cutoff_dt)
    blocked = [
        e for e in all_events if isinstance(e, CandidateBlocked) and e.symbol.upper() == symbol
    ]

    return format_blocked_answer(symbol, blocked, days)

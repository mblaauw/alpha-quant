from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from statistics import mean, stdev
from typing import TYPE_CHECKING, Any

import structlog

from alpha_quant.adapters.real.base_connector import BaseConnector
from alpha_quant.domain.models import MentionCount, SentimentBaseline

if TYPE_CHECKING:
    from alpha_quant.app.vault import Vault

logger = structlog.get_logger()

_COMMON_WORDS: set[str] = {
    "AI",
    "AM",
    "APR",
    "AT",
    "ATM",
    "AUG",
    "CEO",
    "CFO",
    "COO",
    "CTO",
    "DD",
    "DEC",
    "DJT",
    "DM",
    "DOE",
    "EU",
    "EV",
    "FEB",
    "FO",
    "GO",
    "IAN",
    "IMO",
    "IRL",
    "IT",
    "JAN",
    "JUL",
    "JUN",
    "LA",
    "LOL",
    "MAR",
    "MAY",
    "MO",
    "NOV",
    "NTA",
    "NY",
    "OCT",
    "OH",
    "OK",
    "OMG",
    "OP",
    "OR",
    "PE",
    "PM",
    "RH",
    "ROI",
    "SA",
    "SEC",
    "SEP",
    "SO",
    "TA",
    "TL",
    "TLDR",
    "TV",
    "UK",
    "USA",
    "USD",
    "VIP",
    "VS",
    "YE",
    "YTD",
    "YOLO",
}

_REDDIT_UA = "alpha-quant/0.1.0 (research project; contact m@mblaauw.dev)"


class RedditSentimentConnector(BaseConnector):
    def __init__(
        self,
        symbols: list[str],
        *,
        user_agent: str = _REDDIT_UA,
        vault: Vault | None = None,
    ) -> None:
        self._symbols = sorted(symbols)
        self._patterns = {
            sym: re.compile(rf"\b{re.escape(sym)}\b", re.IGNORECASE)
            for sym in self._symbols
            if sym not in _COMMON_WORDS
        }
        super().__init__(
            source_name="reddit",
            base_url="https://www.reddit.com",
            tokens_per_second=0.167,
            max_burst=1,
            timeout_s=15.0,
            user_agent=user_agent,
            vault=vault,
        )

    def parse(self, data: bytes, **kwargs: Any) -> Any:
        return data

    def _fetch_subreddit_new(self, sub: str) -> list[dict[str, Any]]:
        path = f"/r/{sub}/new.json"
        params: dict[str, str] = {"limit": "100"}
        response = self.fetch(f"{self._base_url}{path}", params)
        raw = response.json()
        children = raw.get("data", {}).get("children", [])
        return [
            c["data"] for c in children if isinstance(c, dict) and isinstance(c.get("data"), dict)
        ]

    def _count_mentions(self, posts: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for post in posts:
            title = (post.get("title") or "") or ""
            selftext = (post.get("selftext") or "") or ""
            text = f"{title} {selftext}".upper()
            for sym, pattern in self._patterns.items():
                matches = pattern.findall(text)
                if matches:
                    counts[sym] += len(matches)
        return dict(counts)

    def mention_counts(
        self,
        subreddits: list[str] | None = None,
    ) -> list[MentionCount]:
        if subreddits is None:
            subreddits = ["wallstreetbets", "stocks"]
        today = date.today()
        results: list[MentionCount] = []

        for sub in subreddits:
            try:
                posts = self._fetch_subreddit_new(sub)
                counts = self._count_mentions(posts)
                for sym, count in counts.items():
                    if count > 0:
                        results.append(
                            MentionCount(
                                symbol=sym,
                                date=today,
                                source=f"reddit/{sub}",
                                count=count,
                            )
                        )
            except Exception as exc:
                logger.warning(
                    "reddit_fetch_failed",
                    subreddit=sub,
                    error=str(exc),
                )
                continue

        return results

    def baseline(self, symbol: str) -> SentimentBaseline:
        counts = self.mention_counts()
        relevant = [c.count for c in counts if c.symbol.upper() == symbol.upper()]
        if len(relevant) < 2:
            return SentimentBaseline(
                symbol=symbol.upper(),
                mean_mentions=float(sum(relevant)) if relevant else 0.0,
                std_mentions=0.0,
                z_score=0.0,
            )

        avg = mean(relevant)
        sd = stdev(relevant)
        current = relevant[-1]
        z = (current - avg) / sd if sd > 0 else 0.0
        return SentimentBaseline(
            symbol=symbol.upper(),
            mean_mentions=avg,
            std_mentions=sd,
            z_score=round(z, 4),
        )

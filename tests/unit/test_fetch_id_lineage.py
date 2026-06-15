"""Tests for fetch_id lineage from vault through normalization to canonical storage."""

from datetime import date

import httpx

from alpha_quant.adapters.real.base_connector import FetchResult
from alpha_quant.app.store.schema import model_to_pylist
from alpha_quant.domain.models import (
    Bar,
    CorporateAction,
    EarningsEntry,
    FundamentalsSnapshot,
    InsiderTransaction,
    MentionCount,
)


def test_fetch_result_dataclass() -> None:
    response = httpx.Response(200, content=b"{}")
    fr = FetchResult(response=response, fetch_id="test123")
    assert fr.fetch_id == "test123"
    assert fr.response.status_code == 200


def test_fetch_result_fetch_id_default_none() -> None:
    response = httpx.Response(200, content=b"{}")
    fr = FetchResult(response=response)
    assert fr.fetch_id is None


def test_eodhd_parse_bar_with_fetch_id() -> None:
    from alpha_quant.adapters.real.eodhd_connector import EODHDConnector

    conn = EODHDConnector(api_token="test")
    entry = {
        "date": "2026-01-02",
        "open": 100.0,
        "high": 105.0,
        "low": 95.0,
        "close": 101.0,
        "adjusted_close": 100.5,
        "volume": 1_000_000,
    }
    bar = conn._parse_bar(entry, "AAPL", fetch_id="lineage123")
    assert bar.fetch_id == "lineage123"
    assert bar.symbol == "AAPL"
    assert bar.close == 101.0


def test_bar_model_to_pylist_includes_fetch_id() -> None:
    bar = Bar(
        symbol="AAPL",
        date=date(2026, 1, 1),
        open=100.0,
        high=105.0,
        low=95.0,
        close=101.0,
        volume=1_000_000,
        fetch_id="abc123",
    )
    rows = model_to_pylist([bar], "bars")
    assert rows[0]["fetch_id"] == "abc123"


def test_bar_model_to_pylist_fetch_id_none() -> None:
    bar = Bar(
        symbol="AAPL",
        date=date(2026, 1, 1),
        open=100.0,
        high=105.0,
        low=95.0,
        close=101.0,
        volume=1_000_000,
    )
    rows = model_to_pylist([bar], "bars")
    assert rows[0]["fetch_id"] is None


def test_fundamentals_model_to_pylist_includes_fetch_id() -> None:
    snap = FundamentalsSnapshot(
        symbol="AAPL",
        as_of_date=date(2026, 1, 1),
        market_cap=1e12,
        fetch_id="def456",
    )
    rows = model_to_pylist([snap], "fundamentals")
    assert rows[0]["fetch_id"] == "def456"


def test_insider_model_to_pylist_includes_fetch_id() -> None:
    tx = InsiderTransaction(
        symbol="AAPL",
        owner="CEO",
        transaction_type="Buy",
        shares_traded=1000.0,
        fetch_id="ghi789",
    )
    rows = model_to_pylist([tx], "insider_transactions")
    assert rows[0]["fetch_id"] == "ghi789"


def test_mentions_model_to_pylist_includes_fetch_id() -> None:
    m = MentionCount(
        symbol="AAPL",
        mention_date=date(2026, 1, 1),
        source="reddit",
        count=10,
        fetch_id="jkl012",
    )
    rows = model_to_pylist([m], "mentions")
    assert rows[0]["fetch_id"] == "jkl012"


def test_earnings_model_to_pylist_includes_fetch_id() -> None:
    e = EarningsEntry(
        symbol="AAPL",
        date=date(2026, 1, 1),
        fetch_id="mno345",
    )
    rows = model_to_pylist([e], "earnings")
    assert rows[0]["fetch_id"] == "mno345"


def test_corp_actions_model_to_pylist_includes_fetch_id() -> None:
    ca = CorporateAction(
        symbol="AAPL",
        effective_date=date(2026, 1, 1),
        action_type="SPLIT",
        ratio=2.0,
        fetch_id="pqr678",
    )
    rows = model_to_pylist([ca], "corp_actions")
    assert rows[0]["fetch_id"] == "pqr678"

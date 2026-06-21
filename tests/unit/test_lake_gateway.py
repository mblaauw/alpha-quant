from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from adapters.fake.lake_fixture import FixtureLakeGateway
from adapters.real.lake_data import (
    LakeFundamentals,
    LakeInsiderFeed,
    LakeMarketData,
    LakeSentimentFeed,
)
from ports.clock import Clock


class FixedClock(Clock):
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    def today(self) -> date:
        return self._now.date()

    def market_date(self) -> date:
        return self._now.date()


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), path, compression="zstd")


def _build_lake_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "fixtures" / "v1" / "lake"
    _write(
        root / "bars.parquet",
        [
            {
                "symbol": "AAPL",
                "effective_date": date(2026, 1, 2),
                "available_at": datetime(2026, 1, 2, 22, tzinfo=UTC),
                "open": 100.0,
                "high": 102.0,
                "low": 99.0,
                "close": 101.0,
                "volume": 1_000_000.0,
            },
            {
                "symbol": "AAPL",
                "effective_date": date(2026, 1, 3),
                "available_at": datetime(2026, 1, 5, 22, tzinfo=UTC),
                "open": 110.0,
                "high": 112.0,
                "low": 109.0,
                "close": 111.0,
                "volume": 2_000_000.0,
            },
        ],
    )
    _write(
        root / "fundamentals.parquet",
        [
            {
                "symbol": "AAPL",
                "effective_date": date(2025, 12, 31),
                "available_at": datetime(2026, 1, 2, 12, tzinfo=UTC),
                "market_cap": 3_000_000_000_000.0,
                "sector": "Technology",
                "operating_cash_flow": 100_000_000_000.0,
                "total_debt": 50_000_000_000.0,
                "total_equity": 200_000_000_000.0,
                "accruals": 0.0,
            }
        ],
    )
    _write(
        root / "earnings_calendar.parquet",
        [
            {
                "symbol": "AAPL",
                "effective_date": date(2026, 1, 10),
                "report_date": date(2026, 1, 10),
                "available_at": datetime(2026, 1, 2, 12, tzinfo=UTC),
                "eps_estimate": 2.5,
            }
        ],
    )
    _write(
        root / "insider_tx.parquet",
        [
            {
                "symbol": "AAPL",
                "effective_date": date(2026, 1, 2),
                "available_at": datetime(2026, 1, 2, 12, tzinfo=UTC),
                "owner": "CEO",
                "transaction_type": "Buy",
                "shares_traded": 1000.0,
                "price": 100.0,
            }
        ],
    )
    _write(
        root / "attention_metrics.parquet",
        [
            {
                "symbol": "AAPL",
                "effective_date": date(2026, 1, 1),
                "available_at": datetime(2026, 1, 1, 12, tzinfo=UTC),
                "mention_count": 10,
                "source_id": "fixture_attention",
            },
            {
                "symbol": "AAPL",
                "effective_date": date(2026, 1, 2),
                "available_at": datetime(2026, 1, 2, 12, tzinfo=UTC),
                "mention_count": 20,
                "source_id": "fixture_attention",
            },
        ],
    )
    return root.parent


def test_fixture_lake_gateway_honors_as_of(tmp_path: Path) -> None:
    gateway = FixtureLakeGateway(_build_lake_fixture(tmp_path))
    as_of = datetime(2026, 1, 3, 12, tzinfo=UTC)

    bars = gateway.bars("AAPL", date(2026, 1, 1), date(2026, 1, 5), as_of)
    latest = gateway.latest_bar("AAPL", as_of)

    assert [bar.date for bar in bars] == [date(2026, 1, 2)]
    assert bars[0].close == 101.0
    assert latest is not None
    assert latest.close == 101.0


def test_fixture_lake_gateway_maps_domain_models(tmp_path: Path) -> None:
    gateway = FixtureLakeGateway(_build_lake_fixture(tmp_path))
    as_of = datetime(2026, 1, 3, 12, tzinfo=UTC)

    fundamentals = gateway.fundamentals("AAPL", as_of)
    earnings = gateway.earnings_calendar(date(2026, 1, 1), date(2026, 1, 31), as_of)
    insider = gateway.insider_transactions("AAPL", as_of)
    mentions = gateway.mention_counts("AAPL", days=3, as_of=as_of)

    assert fundamentals is not None
    assert fundamentals.sector == "Technology"
    assert earnings[0].date == date(2026, 1, 10)
    assert insider[0].owner == "CEO"
    assert [mention.count for mention in mentions] == [10, 20]


def test_lake_data_ports_use_clock_as_of(tmp_path: Path) -> None:
    gateway = FixtureLakeGateway(_build_lake_fixture(tmp_path))
    clock = FixedClock(datetime(2026, 1, 3, 12, tzinfo=UTC))

    market_data = LakeMarketData(gateway, clock)
    fundamentals = LakeFundamentals(gateway, clock)
    insider = LakeInsiderFeed(gateway, clock)
    sentiment = LakeSentimentFeed(gateway, clock)

    bars = market_data.daily_bars("AAPL", date(2026, 1, 1), date(2026, 1, 5))
    quote = market_data.latest_quote("AAPL")

    assert [bar.close for bar in bars] == [101.0]
    assert quote.price == 101.0
    assert fundamentals.snapshot("AAPL").sector == "Technology"
    assert insider.cluster_transactions("AAPL")[0].shares_traded == 1000.0
    assert sentiment.baseline("AAPL").mean_mentions == 15.0

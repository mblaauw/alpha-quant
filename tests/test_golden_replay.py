"""Golden replay test — deterministic DailyCycleService run against fixture data."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

import pytest

from alpha_quant.adapters.fake.alpha_lake_http_fixture import AlphaLakeHttpFixtureClient
from alpha_quant.adapters.fake.operational_store import FakeOperationalStore
from alpha_quant.adapters.fake.virtual_clock import VirtualClock
from alpha_quant.application.daily_cycle import DailyCycleService

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
GOLDEN_HASH_PATH = FIXTURES_DIR / "golden" / "run.hash"


def _deterministic_hash(
    scorecards: list,
    result,
) -> str:
    """SHA-256 of deterministic fields (excludes facts_hash, IDs, timestamps)."""
    data = {
        "scorecards": [
            {
                "symbol": sc.symbol,
                "security_id": sc.security_id,
                "config_hash": sc.config_hash,
                "strategy_version": sc.strategy_version,
                "recommendation": sc.recommendation.value,
                "confidence": sc.confidence,
                "total_score": sc.total_score,
                "data_quality": sc.data_quality.value,
                "components": [
                    {
                        "name": c.name,
                        "score": c.score,
                        "state": c.state.value,
                        "weight": c.weight,
                        "passed": c.passed,
                    }
                    for c in sc.components
                ],
            }
            for sc in sorted(scorecards, key=lambda x: x.symbol)
        ],
        "result": {
            "scorecard_count": result.scorecard_count,
            "regime": result.regime,
            "prev_equity": str(result.prev_equity),
            "new_equity": str(result.new_equity),
            "halted": result.halted,
        },
    }
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


class TestGoldenReplay:
    @pytest.fixture
    def store(self) -> FakeOperationalStore:
        return FakeOperationalStore()

    @pytest.fixture
    def lake(self) -> AlphaLakeHttpFixtureClient:
        return AlphaLakeHttpFixtureClient(FIXTURES_DIR / "v1")

    def test_golden_replay(
        self, store: FakeOperationalStore, lake: AlphaLakeHttpFixtureClient
    ) -> None:
        as_of = datetime(2026, 1, 5, 14, 0, 0)
        clock = VirtualClock(as_of.date())
        service = DailyCycleService(lake, store, clock)

        book_id = UUID("00000000-0000-0000-0000-000000000001")

        result = service.run(
            book_id=book_id,
            as_of=as_of,
            run_key="golden-test-run",
            discovery_symbols=["AAPL", "MSFT"],
        )

        scorecards = store.load_scorecards_for_run(str(result.decision_run_id))
        h = _deterministic_hash(scorecards, result)

        if GOLDEN_HASH_PATH.exists():
            expected = GOLDEN_HASH_PATH.read_text().strip()
            assert h == expected, (
                f"Golden hash mismatch!\n"
                f"  Got:      {h}\n"
                f"  Expected: {expected}\n"
                f"  Run `make bless-golden` to update the golden hash."
            )
        else:
            GOLDEN_HASH_PATH.parent.mkdir(parents=True, exist_ok=True)
            GOLDEN_HASH_PATH.write_text(h)
            pytest.fail(
                f"Golden hash file created at {GOLDEN_HASH_PATH} with:\n"
                f"  {h}\n"
                f"Review and commit this file."
            )

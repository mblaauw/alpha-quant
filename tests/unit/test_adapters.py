from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from adapters.real.event_sink import SqliteEventSink
from adapters.real.token_bucket import TokenBucket
from domain.events import (
    CandidateBlocked,
    CandidateScored,
    PipelineRunStarted,
)


class TestTokenBucket:
    def test_consume_initial_tokens(self) -> None:
        tb = TokenBucket(tokens_per_second=10.0, max_burst=5.0)
        for _ in range(5):
            assert tb.consume(), "should allow up to max_burst"

    def test_consume_exhausted(self) -> None:
        tb = TokenBucket(tokens_per_second=1.0, max_burst=1.0)
        assert tb.consume()
        assert not tb.consume()

    def test_wait_time_zero_when_tokens_available(self) -> None:
        tb = TokenBucket(tokens_per_second=1.0, max_burst=1.0)
        assert tb.wait_time() == 0.0

    def test_wait_time_positive_when_exhausted(self) -> None:
        tb = TokenBucket(tokens_per_second=2.0, max_burst=1.0)
        tb.consume()
        assert tb.wait_time() > 0.0

    def test_consume_with_multiple_tokens(self) -> None:
        tb = TokenBucket(tokens_per_second=1.0, max_burst=5.0)
        assert tb.consume(3.0)
        assert tb.consume(2.0)
        assert not tb.consume(1.0)

    def test_zero_rate_allows_none(self) -> None:
        tb = TokenBucket(tokens_per_second=0.0, max_burst=0.0)
        assert not tb.consume()


class TestSqliteEventSink:
    def test_instantiate(self, tmp_path: Path) -> None:
        db = tmp_path / "events.db"
        sink = SqliteEventSink(db)
        assert sink is not None
        sink.close()

    def test_emit_and_query(self, tmp_path: Path) -> None:
        db = tmp_path / "events.db"
        sink = SqliteEventSink(db)
        event = CandidateScored(
            event_id="evt-1",
            run_id="run-1",
            timestamp=datetime.now(timezone.utc),
            source="test",
            symbol="AAPL",
            composite_score=0.75,
            components={},
        )
        sink.emit(event)
        results = sink.query(run_id="run-1")
        assert len(results) == 1
        assert results[0].event_id == "evt-1"
        sink.close()

    def test_query_empty(self, tmp_path: Path) -> None:
        db = tmp_path / "events.db"
        sink = SqliteEventSink(db)
        results = sink.query(run_id="nonexistent")
        assert results == []
        sink.close()

    def test_emit_multiple_events(self, tmp_path: Path) -> None:
        db = tmp_path / "events.db"
        sink = SqliteEventSink(db)
        now = datetime.now(timezone.utc)
        events = [
            PipelineRunStarted(
                event_id=f"evt-{i}",
                run_id="run-1",
                timestamp=now,
                source="test",
                mode="daily",
            )
            for i in range(3)
        ]
        for e in events:
            sink.emit(e)
        results = sink.query(run_id="run-1")
        assert len(results) == 3
        sink.close()

    def test_query_by_event_type(self, tmp_path: Path) -> None:
        db = tmp_path / "events.db"
        sink = SqliteEventSink(db)
        now = datetime.now(timezone.utc)
        sink.emit(
            CandidateScored(
                event_id="e1",
                run_id="r1",
                timestamp=now,
                source="test",
                symbol="AAPL",
                composite_score=0.75,
                components={},
            )
        )
        sink.emit(
            CandidateBlocked(
                event_id="e2",
                run_id="r1",
                timestamp=now,
                source="test",
                symbol="TSLA",
                gate="risk",
                reason="max_positions",
            )
        )
        scored = sink.query(run_id="r1", event_type="candidate_scored")
        assert len(scored) == 1
        assert scored[0].event_id == "e1"
        sink.close()

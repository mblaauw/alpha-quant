from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from adapters.fake.fixture_store import FixtureStore
from adapters.real.event_sink import SqliteEventSink
from adapters.real.token_bucket import TokenBucket
from domain.events import (
    CandidateBlocked,
    CandidateScored,
    PipelineRunStarted,
)
from domain.models import Bar, Decision


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


class TestFixtureStore:
    def test_instantiate(self) -> None:
        store = FixtureStore()
        assert store is not None

    def test_save_and_load_bars(self) -> None:
        store = FixtureStore()
        bar = Bar(symbol="AAPL", date=date(2026, 1, 1), open=10.0, high=11.0, low=9.0, close=10.5, volume=1_000_000)
        store.save_bars("AAPL", [bar])
        loaded = store.load_bars("AAPL", date(2025, 1, 1), date(2027, 1, 1))
        assert len(loaded) == 1
        assert loaded[0].symbol == "AAPL"
        assert loaded[0].close == 10.5

    def test_save_and_load_decisions(self) -> None:
        store = FixtureStore()
        decision = Decision(
            symbol="AAPL",
            date=date(2026, 1, 1),
            action="enter",
            confidence=0.8,
        )
        store.save_decision(decision)
        loaded = store.load_decisions("AAPL", date(2025, 1, 1))
        assert len(loaded) == 1
        assert loaded[0].action == "enter"

    def test_empty_decisions(self) -> None:
        store = FixtureStore()
        assert store.load_decisions("AAPL", date(2025, 1, 1)) == []

    def test_quarantine_lifecycle(self) -> None:
        store = FixtureStore()
        store.add_quarantine("AAPL", "max_drawdown", severity="HALT")
        q = store.list_quarantine(cleared=False)
        assert len(q) == 1
        assert q[0]["symbol"] == "AAPL"
        store.clear_quarantine("AAPL")
        q = store.list_quarantine(cleared=False)
        assert len(q) == 0
        q = store.list_quarantine(cleared=True)
        assert len(q) == 1
        assert q[0]["symbol"] == "AAPL"

    def test_run_lifecycle(self) -> None:
        store = FixtureStore()
        run_id = store.register_run("daily", "abc123")
        assert run_id.startswith("fixture-run-")
        store.complete_run(run_id, status="completed")
        runs = store.list_runs()
        assert len(runs) == 1
        assert runs[0]["run_id"] == run_id

    def test_transaction_context(self) -> None:
        store = FixtureStore()
        with store.transaction() as tx:
            assert tx is store


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
                event_id=f"evt-{i}", run_id="run-1",
                timestamp=now, source="test", mode="daily",
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
        sink.emit(CandidateScored(event_id="e1", run_id="r1", timestamp=now, source="test", symbol="AAPL", composite_score=0.75, components={}))
        sink.emit(CandidateBlocked(event_id="e2", run_id="r1", timestamp=now, source="test", symbol="TSLA", gate="risk", reason="max_positions"))
        scored = sink.query(run_id="r1", event_type="candidate_scored")
        assert len(scored) == 1
        assert scored[0].event_id == "e1"
        sink.close()
